import React from "react";
import { staticFile } from "remotion";
import { loadFont } from "@remotion/google-fonts/OpenSans";
import { CROP_KEY, tg } from "./theme";

const { fontFamily } = loadFont("normal", { weights: ["400", "600", "700"], subsets: ["latin"] });

export type Message = {
  from: "user" | "bot";
  time: string;
  text?: string; // user messages: plain text
  html?: string; // bot messages: Telegram HTML as the bot sent it
  buttons?: string[][];
  photo?: string;
  document?: { name: string; size: string };
};

export type ChatProps = { width: number; messages: Message[]; date?: string };

const escapeHtml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** Telegram highlights /commands, @mentions and links; do the same outside <code>. */
const linkify = (html: string) => {
  let inCode = false;
  return html
    .split(/(<[^>]+>)/)
    .map((part) => {
      if (part.startsWith("<")) {
        if (part === "<code>") inCode = true;
        if (part === "</code>") inCode = false;
        return part;
      }
      if (inCode) return part;
      return part
        .replace(/https?:\/\/[^\s<]+/g, (url) => `<span class="link">${url}</span>`)
        .replace(/(^|[\s(])(\/[a-z_]+)(?![\w/])/g, '$1<span class="link">$2</span>')
        .replace(/(^|[\s(])(@\w{3,})/g, '$1<span class="link">$2</span>');
    })
    .join("");
};

const Ticks: React.FC = () => (
  <svg width="16" height="11" viewBox="0 0 16 11" style={{ marginLeft: 3 }}>
    <path d="M1 6l3 3 6-7M6 9l1 1 7-8" stroke={tg.outgoingMuted} strokeWidth="1.5" fill="none" />
  </svg>
);

const Time: React.FC<{ value: string; outgoing: boolean }> = ({ value, outgoing }) => (
  <span
    style={{
      float: "right",
      display: "inline-flex",
      alignItems: "center",
      marginLeft: 12,
      marginTop: 6,
      fontSize: 12,
      color: outgoing ? tg.outgoingMuted : tg.muted,
    }}
  >
    {value}
    {outgoing && <Ticks />}
  </span>
);

const DocumentIcon: React.FC = () => (
  <div
    style={{
      width: 48,
      height: 48,
      borderRadius: 24,
      background: "#4a9fdd",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
    }}
  >
    <svg width="20" height="24" viewBox="0 0 20 24">
      <path d="M2 0h11l7 7v15a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2z" fill="#fff" />
      <path d="M13 0v7h7" fill="#cfe6f7" />
    </svg>
  </div>
);

const Bubble: React.FC<{ message: Message; maxWidth: number }> = ({ message, maxWidth }) => {
  const outgoing = message.from === "user";
  const html = linkify(message.html ?? escapeHtml(message.text ?? ""));
  const hasText = html.trim().length > 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: outgoing ? "flex-end" : "flex-start" }}>
      <div
        style={{
          background: outgoing ? tg.outgoing : tg.incoming,
          borderRadius: 12,
          maxWidth,
          overflow: "hidden",
          boxShadow: "0 1px 1px rgba(0,0,0,.25)",
        }}
      >
        {message.photo && <img src={staticFile(message.photo)} style={{ display: "block", width: maxWidth }} />}
        {message.document && (
          <div style={{ display: "flex", gap: 14, alignItems: "center", padding: "12px 14px 0" }}>
            <DocumentIcon />
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{message.document.name}</div>
              <div style={{ color: tg.muted, fontSize: 13, marginTop: 2 }}>{message.document.size}</div>
            </div>
          </div>
        )}
        <div style={{ padding: "8px 12px 7px", fontSize: 14, lineHeight: "19px" }}>
          {hasText && <span className="msg" dangerouslySetInnerHTML={{ __html: html }} />}
          <Time value={message.time} outgoing={outgoing} />
          <div style={{ clear: "both" }} />
        </div>
      </div>
      {message.buttons && (
        <div style={{ width: maxWidth, display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
          {message.buttons.map((row, i) => (
            <div key={i} style={{ display: "flex", gap: 4 }}>
              {row.map((label) => (
                <div
                  key={label}
                  style={{
                    flex: 1,
                    background: tg.button,
                    borderRadius: 8,
                    padding: "9px 6px",
                    textAlign: "center",
                    fontWeight: 600,
                    fontSize: 14,
                  }}
                >
                  {label}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const Header: React.FC = () => (
  <div style={{ background: tg.header, height: 56, display: "flex", alignItems: "center", padding: "0 16px", gap: 14 }}>
    <svg width="18" height="16" viewBox="0 0 18 16">
      <path d="M8 1L1 8l7 7M1 8h17" stroke={tg.muted} strokeWidth="2" fill="none" />
    </svg>
    <div
      style={{
        width: 40,
        height: 40,
        borderRadius: 20,
        background: tg.avatar,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontWeight: 600,
        fontSize: 18,
      }}
    >
      T
    </div>
    <div style={{ flex: 1 }}>
      <div style={{ fontWeight: 600, fontSize: 15 }}>Teleword</div>
      <div style={{ color: tg.muted, fontSize: 13 }}>bot</div>
    </div>
    <svg width="20" height="20" viewBox="0 0 20 20">
      <circle cx="8" cy="8" r="6" stroke={tg.muted} strokeWidth="2" fill="none" />
      <path d="M13 13l5 5" stroke={tg.muted} strokeWidth="2" />
    </svg>
    <svg width="6" height="20" viewBox="0 0 6 20" style={{ marginLeft: 8 }}>
      {[3, 10, 17].map((y) => (
        <circle key={y} cx="3" cy={y} r="2" fill={tg.muted} />
      ))}
    </svg>
  </div>
);

const InputBar: React.FC = () => (
  <div style={{ background: tg.header, height: 52, display: "flex", alignItems: "center", padding: "0 12px", gap: 14 }}>
    <div style={{ background: tg.menu, borderRadius: 16, padding: "5px 14px", fontWeight: 600, fontSize: 14 }}>Menu</div>
    <svg width="18" height="20" viewBox="0 0 18 20">
      <path
        d="M15 9l-6.5 6.5a4 4 0 0 1-5.7-5.7L9.6 3a2.7 2.7 0 0 1 3.8 3.8L6.8 13.4a1.3 1.3 0 0 1-1.9-1.9L11 5.4"
        stroke={tg.muted}
        strokeWidth="1.6"
        fill="none"
      />
    </svg>
    <div style={{ flex: 1, color: tg.muted, fontSize: 14 }}>Write a message...</div>
  </div>
);

export const Chat: React.FC<ChatProps> = ({ width, messages, date }) => {
  const maxWidth = Math.min(440, Math.round(width * 0.78));
  return (
    <div style={{ width, height: "100%", background: CROP_KEY, fontFamily, color: tg.text }}>
      <style>{`
        .msg { white-space: pre-wrap; word-wrap: break-word; }
        .msg b { font-weight: 700; }
        .msg code { font-family: Menlo, Consolas, monospace; font-size: 13px; color: ${tg.code}; }
        .link { color: ${tg.link}; }
      `}</style>
      <Header />
      <div style={{ background: tg.background, padding: "14px 14px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
        {date && (
          <div style={{ alignSelf: "center", background: "#1e2c3a", borderRadius: 12, padding: "3px 12px", fontWeight: 600, fontSize: 13 }}>
            {date}
          </div>
        )}
        {messages.map((m, i) => (
          <Bubble key={i} message={m} maxWidth={maxWidth} />
        ))}
      </div>
      <InputBar />
    </div>
  );
};
