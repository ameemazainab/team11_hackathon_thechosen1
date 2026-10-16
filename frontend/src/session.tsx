import { createContext, useContext } from "react";
import type { Me, Meta } from "./api";

export interface Session {
  me: Me;
  meta: Meta;
  reloadMeta: () => void;
  switchUser: (code: string) => Promise<void>;
  logout: () => Promise<void>;
}
export const SessionCtx = createContext<Session | null>(null);
export function useSession(): Session {
  const s = useContext(SessionCtx);
  if (!s) throw new Error("No session");
  return s;
}
