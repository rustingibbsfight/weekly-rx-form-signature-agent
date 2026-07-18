import { defineTool } from "eve/tools";
import { z } from "zod";

const TZ = "America/Los_Angeles";

function pacificDate(daysFromToday = 0): Date {
  const now = new Date(Date.now() + daysFromToday * 86_400_000);
  // Re-anchor to the Pacific calendar date so weekday math is correct.
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return new Date(`${get("year")}-${get("month")}-${get("day")}T12:00:00Z`);
}

function nameVariants(d: Date): string[] {
  const month = d.getUTCMonth() + 1;
  const day = d.getUTCDate();
  const year = d.getUTCFullYear();
  const monthName = d.toLocaleDateString("en-US", { month: "long", timeZone: "UTC" });
  const pad = (n: number) => String(n).padStart(2, "0");
  return [
    `${month}/${day}`,
    `${month}-${day}`,
    `${pad(month)}/${pad(day)}`,
    `${pad(month)}-${pad(day)}`,
    `${month}/${day}/${year}`,
    `${pad(month)}-${pad(day)}-${year}`,
    `${year}-${pad(month)}-${pad(day)}`,
    `${monthName} ${day}`,
    `${monthName} ${day}, ${year}`,
  ];
}

export default defineTool({
  description:
    "Get today's date in Pacific time, the dates covering the current week, and common date-name variants. Use this to fuzzy-match the current week's dated Rx forms subfolder in Google Drive.",
  inputSchema: z.object({}),
  execute() {
    const today = pacificDate();
    // This week's Saturday (the scheduled run day). If today is Saturday, that's today.
    const daysUntilSaturday = (6 - today.getUTCDay() + 7) % 7;
    const saturday = pacificDate(daysUntilSaturday);
    const week = Array.from({ length: 8 }, (_, i) => {
      const d = pacificDate(daysUntilSaturday - i); // Saturday back through last Saturday
      return {
        date: d.toISOString().slice(0, 10),
        weekday: d.toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" }),
        nameVariants: nameVariants(d),
      };
    });
    return {
      timezone: TZ,
      today: today.toISOString().slice(0, 10),
      todayWeekday: today.toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" }),
      thisSaturday: saturday.toISOString().slice(0, 10),
      currentWeekDatesNewestFirst: week,
    };
  },
});
