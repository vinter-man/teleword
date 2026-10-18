import React from "react";
import { Still } from "remotion";
import { Chat, ChatProps } from "./Chat";
import { Terminal, TerminalProps } from "./Terminal";

// Frames are rendered taller than needed; render.mjs crops them at the CROP_KEY colour.
const MAX_HEIGHT = 2400;

type Sized = { width: number };

export const Root: React.FC = () => (
  <>
    <Still
      id="Chat"
      component={Chat}
      width={600}
      height={MAX_HEIGHT}
      defaultProps={{ width: 600, messages: [] } as ChatProps & Sized}
      calculateMetadata={({ props }) => ({ width: props.width })}
    />
    <Still
      id="Terminal"
      component={Terminal}
      width={1000}
      height={MAX_HEIGHT}
      defaultProps={{ width: 1000, lines: [] } as TerminalProps & Sized}
      calculateMetadata={({ props }) => ({ width: props.width })}
    />
  </>
);
