import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterNextRender,
  input,
  signal,
  viewChild,
} from "@angular/core";

import { LinkModule, TypographyModule } from "@bitwarden/components";

type DownloadAsset = {
  id: string;
  name: string;
  platforms: string[];
  kind: string;
  filename: string | null;
  version: string | null;
  status: "published" | "unavailable";
  channel: string;
  sha256: string | null;
  size: number | null;
  url: string | null;
  docsUrl: string;
  install: string;
  reason: string | null;
  qr: boolean;
};

type DownloadManifest = {
  schema: number;
  generatedAt: string;
  note: string;
  refused: string[];
  assets: DownloadAsset[];
};

type QrCtor = new (opts: { element: HTMLCanvasElement; value: string; size: number }) => void;

/**
 * QR for one published download. Uses the vault's bundled qrious script.
 * The value is the install URL only. No request is sent to a QR service.
 */
@Component({
  selector: "app-download-qr",
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <canvas
      #code
      width="168"
      height="168"
      role="img"
      [attr.aria-label]="label()"
    ></canvas>
  `,
})
export class DownloadQrComponent {
  readonly url = input.required<string>();
  readonly label = input.required<string>();
  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>("code");

  constructor() {
    afterNextRender(() => {
      void drawQr(this.canvas().nativeElement, this.url());
    });
  }
}

@Component({
  selector: "app-downloads",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TypographyModule, LinkModule, DownloadQrComponent],
  template: `
    <main class="tw-mx-auto tw-mt-6 tw-w-full tw-max-w-3xl tw-px-4 tw-pb-10" data-testid="downloads-page">
      <h1 bitTypography="h1">Downloads</h1>
      <p bitTypography="body1">
        Installers appear here only after a build publishes the file and its sha256. Store listings
        for other password managers are not Komboe, and unpublished platforms stay on this page as
        unavailable.
      </p>
      @if (error()) {
        <p role="alert">{{ error() }}</p>
      }
      @if (manifest(); as data) {
        <p bitTypography="body2">Manifest generated {{ data.generatedAt }}.</p>
        <p bitTypography="body2">{{ data.note }}</p>
        <div class="tw-mt-4 tw-flex tw-flex-col tw-gap-4">
          @for (asset of data.assets; track asset.id) {
            <section
              class="tw-rounded-xl tw-border tw-border-solid tw-border-secondary-300 tw-p-4"
              [attr.data-testid]="'download-' + asset.id"
            >
              <h2 bitTypography="h3" class="tw-mt-0">{{ asset.name }}</h2>
              <p>{{ asset.platforms.join(", ") }}</p>
              @if (asset.status === "published" && asset.url) {
                <p>
                  <span class="tw-font-semibold">Unsigned testing build</span>
                  @if (asset.version) {
                    <span> · version {{ asset.version }}</span>
                  }
                </p>
                <p>
                  <a
                    bitLink
                    [href]="absolute(asset.url)"
                    [attr.data-testid]="'download-link-' + asset.id"
                    [attr.aria-label]="'Download ' + asset.name"
                  >
                    Download {{ asset.filename }}
                  </a>
                </p>
                @if (asset.sha256) {
                  <p class="tw-break-all">
                    <span class="tw-font-semibold">sha256</span> {{ asset.sha256 }}
                  </p>
                }
                @if (asset.size != null) {
                  <p>{{ asset.size }} bytes</p>
                }
                @if (asset.install) {
                  <p>{{ asset.install }}</p>
                }
                @if (asset.qr) {
                  <app-download-qr
                    [url]="absolute(asset.url)"
                    [label]="'QR code for ' + asset.name + '. The download link above is the same file.'"
                  ></app-download-qr>
                }
              } @else {
                <p>
                  <span class="tw-font-semibold">Not available.</span>
                  {{ asset.reason }}
                </p>
              }
              @if (asset.docsUrl) {
                <p>
                  <a bitLink [href]="asset.docsUrl" target="_blank" rel="noreferrer">
                    @if (asset.kind === "extension") {
                      Manual install instructions
                    } @else {
                      Source and notes
                    }
                  </a>
                </p>
              }
            </section>
          }
        </div>
      }
    </main>
  `,
})
export class DownloadsComponent {
  protected readonly manifest = signal<DownloadManifest | null>(null);
  protected readonly error = signal<string | null>(null);

  constructor() {
    afterNextRender(() => {
      void this.load();
    });
  }

  protected absolute(url: string): string {
    return new URL(url, document.baseURI).href;
  }

  private async load(): Promise<void> {
    try {
      const response = await fetch(new URL("komboe-downloads.json", document.baseURI).href);
      if (!response.ok) {
        this.error.set("The downloads manifest did not load.");
        return;
      }
      this.manifest.set((await response.json()) as DownloadManifest);
    } catch {
      this.error.set("The downloads manifest did not load.");
    }
  }
}

function drawQr(canvas: HTMLCanvasElement, value: string): Promise<void> {
  const fromWindow = () => (window as unknown as { QRious?: QrCtor }).QRious;
  const paint = (ctor: QrCtor) => {
    new ctor({ element: canvas, value, size: 168 });
  };
  const ready = fromWindow();
  if (ready) {
    paint(ready);
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = new URL("scripts/qrious.min.js", document.baseURI).href;
    script.onload = () => {
      const ctor = fromWindow();
      if (ctor) {
        paint(ctor);
      }
      resolve();
    };
    script.onerror = () => resolve();
    document.head.appendChild(script);
  });
}
