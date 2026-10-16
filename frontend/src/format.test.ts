import { describe, expect, it } from "vitest";
import { fiscalYear, monthLabel, money, parseValue } from "./format";

describe("parseValue (FR-05)", () => {
  it("rejects formulas, text and negatives", () => {
    expect(parseValue("=90000-55000").ok).toBe(false);
    expect(parseValue("abc").ok).toBe(false);
    expect(parseValue("-5")).toEqual({ ok: false, error: "Revenue cannot be negative." });
  });
  it("accepts numbers with $ and commas, and blanks", () => {
    expect(parseValue("$1,250.555")).toEqual({ ok: true, value: 1250.56 });
    expect(parseValue("")).toEqual({ ok: true, value: null });
  });
});
describe("formatting", () => {
  it("formats money and months", () => {
    expect(money(-1234.5)).toBe("-$1,235");
    expect(monthLabel("2026-11")).toBe("Nov 26");
  });
  it("uses an April to March fiscal year", () => {
    expect(fiscalYear("2026-03")).toBe("FY26");
    expect(fiscalYear("2026-04")).toBe("FY27");
    expect(fiscalYear("2027-03")).toBe("FY27");
  });
});
