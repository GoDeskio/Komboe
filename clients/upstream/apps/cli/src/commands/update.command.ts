// FIXME: Update this file to be type safe and remove this and next line
// @ts-strict-ignore
import { ApiService } from "@bitwarden/common/abstractions/api.service";
import { PlatformUtilsService } from "@bitwarden/common/platform/abstractions/platform-utils.service";

import { Response } from "../models/response";
import { MessageResponse } from "../models/response/message.response";

const UPDATE_COMMAND = "npm install -g @bitwarden/cli";

export class UpdateCommand {
  inPkg = false;

  constructor(
    private platformUtilsService: PlatformUtilsService,
    protected apiService: ApiService,
  ) {
    this.inPkg = !!(process as any).pkg;
  }

  async run(): Promise<Response> {
    // Off until the operator points this at a GitHub-compatible releases API
    // they host. The CLI does not contact Komboe, Bitwarden, or GitHub on its own.
    const endpoint = process.env.KOMBOE_CLI_RELEASES_URL;
    if (endpoint == null || endpoint === "") {
      const response = new MessageResponse(null, null);
      response.title = "Update checks are off.";
      response.message =
        "Set KOMBOE_CLI_RELEASES_URL to a GitHub-compatible releases API that you host. " +
        "Nothing is contacted until you do.";
      response.noColor = true;
      return Response.success(response);
    }

    const response = await this.apiService.nativeFetch(new Request(endpoint));
    if (response.status !== 200) {
      return Response.error("Error contacting update API: " + response.status);
    }

    const responseJson = await response.json();
    const cliRelease = responseJson.find((r: any) => r.tag_name.includes("cli"));
    if (cliRelease === undefined || cliRelease === null) {
      return Response.error("Could not find latest CLI version.");
    }

    const currentVersion = await this.platformUtilsService.getApplicationVersion();
    if (cliRelease.tag_name === "cli-v" + currentVersion) {
      const response = new MessageResponse(null, null);
      response.title = "No update available.";
      response.noColor = true;
      return Response.success(response);
    }

    const res = this.getFoundUpdateResponse(cliRelease, endpoint);
    return Response.success(res);
  }

  private getFoundUpdateResponse(release: any, endpoint: string) {
    const downloadUrl = this.getDownloadUrl(release.assets, endpoint);

    const response = new MessageResponse(null, null);
    response.title = "A new version is available: " + release.tag_name;
    response.raw = downloadUrl;
    response.message = this.getMessage(release, downloadUrl);

    return response;
  }

  private getMessage(release: any, downloadUrl: string) {
    let message = "";

    if (release.body != null && release.body !== "") {
      message = release.body + "\n\n";
    }

    message += "You can download this update at " + downloadUrl;

    if (this.inPkg) {
      message +=
        "\n\nIf you installed this CLI through a package manager " +
        "you should probably update using its update command instead.";
    } else {
      message +=
        "\n\nIf you installed this CLI through NPM " +
        "you should update using `" +
        UPDATE_COMMAND +
        "`";
    }

    return message;
  }

  private getDownloadUrl(assets: any, fallbackUrl: string) {
    if (assets == null) {
      return fallbackUrl;
    }

    let downloadUrl: string = fallbackUrl;

    for (const a of assets) {
      const download: string = a.browser_download_url;
      if (download == null) {
        continue;
      }

      if (download.indexOf(".zip") === -1) {
        continue;
      }

      if (process.platform === "win32" && download.indexOf("bw-windows") > -1) {
        downloadUrl = download;
        break;
      } else if (process.platform === "darwin" && download.indexOf("bw-macos") > -1) {
        downloadUrl = download;
        break;
      } else if (process.platform === "linux" && download.indexOf("bw-linux") > -1) {
        downloadUrl = download;
        break;
      }
    }

    return downloadUrl;
  }
}
