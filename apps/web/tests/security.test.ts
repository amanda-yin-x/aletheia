import { describe, expect, it } from "vitest";
import { mutationRequestIsTrusted, parseApiOrigin, safeNextPath } from "@/lib/security";

describe("request security", () => {
  it("rejects external and protocol-relative redirects", () => {
    expect(safeNextPath("https://evil.example/path")).toBe("/demo");
    expect(safeNextPath("//evil.example/path")).toBe("/demo");
    expect(safeNextPath("/projects/123/overview?tab=rules")).toBe("/projects/123/overview?tab=rules");
  });

  it("requires matching Origin and double-submit token for mutations", () => {
    const valid = { method: "POST", requestOrigin: "https://aletheia.example", expectedOrigin: "https://aletheia.example", csrfHeader: "token", csrfCookie: "token", secFetchSite: "same-origin" };
    expect(mutationRequestIsTrusted(valid)).toBe(true);
    expect(mutationRequestIsTrusted({ ...valid, requestOrigin: "https://evil.example" })).toBe(false);
    expect(mutationRequestIsTrusted({ ...valid, csrfHeader: "wrong" })).toBe(false);
    expect(mutationRequestIsTrusted({ ...valid, secFetchSite: "cross-site" })).toBe(false);
  });

  it("requires TLS for the production API origin", () => {
    expect(parseApiOrigin("https://aletheia-api.onrender.com", true)?.origin).toBe("https://aletheia-api.onrender.com");
    expect(parseApiOrigin("http://aletheia-api.onrender.com", true)).toBeNull();
    expect(parseApiOrigin("http://localhost:8000", false)?.origin).toBe("http://localhost:8000");
    expect(parseApiOrigin("https://name:password@example.com", true)).toBeNull();
    expect(parseApiOrigin("https://example.com/unexpected-path", true)).toBeNull();
  });
});
