import { Telegraf } from "telegraf";

const token = process.env.TELEGRAM_BOT_TOKEN;

if (!token) {
  throw new Error("TELEGRAM_BOT_TOKEN is required");
}

const bot = new Telegraf(token);

bot.start((ctx) => ctx.reply("Hello from an AdBotHost Node.js bot."));
bot.on("text", (ctx) => ctx.reply(`Echo: ${ctx.message.text}`));

bot.launch();

process.once("SIGINT", () => bot.stop("SIGINT"));
process.once("SIGTERM", () => bot.stop("SIGTERM"));
