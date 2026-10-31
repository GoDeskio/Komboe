import { sendViews } from "./send-views";

describe("sendViews", () => {
  it("shows count only when unlimited", () => {
    expect(sendViews(4, null)).toEqual({ label: "4", remaining: null });
    expect(sendViews(undefined, undefined)).toEqual({ label: "0", remaining: null });
  });

  it("shows used / max and remaining", () => {
    expect(sendViews(3, 10)).toEqual({ label: "3 / 10", remaining: 7 });
  });

  it("never reports negative remaining", () => {
    expect(sendViews(12, 10)).toEqual({ label: "12 / 10", remaining: 0 });
  });
});
