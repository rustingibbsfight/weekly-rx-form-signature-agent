import { defineSchedule } from "eve/schedules";

import slack from "../channels/slack";

// Vercel evaluates cron in UTC. 23:00 UTC Saturday = 4:00 pm Pacific during
// daylight time (Mar–Nov). During standard time (Nov–Mar) it fires at 3:00 pm
// Pacific; switch to "0 0 * * 0" if the 4:00 pm wall-clock time matters year-round.
export default defineSchedule({
  cron: "0 23 * * 6",
  async run({ to, waitUntil, appAuth }) {
    const channelId = process.env.SLACK_CHANNEL_ID;
    if (!channelId) {
      console.warn(
        "weekly-rx-forms: SLACK_CHANNEL_ID is not set; skipping the scheduled run.",
      );
      return;
    }
    waitUntil(
      to(slack, { channelId }).send(
        "Scheduled weekly run: process this week's Rx forms. " +
          "Find this week's dated subfolder in the fightweightgain Drive Rx forms folder, " +
          "generate the fillable intake/prescription PDFs for any consult forms that don't have one yet, " +
          "upload them back to the same folder, and post a summary here. " +
          "If this week's folder or consult forms are missing, ask the team to download them into Drive.",
        { auth: appAuth },
      ),
    );
  },
});
