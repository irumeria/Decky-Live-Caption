// Adapted from neatsorg/livetranslate-decky, GPL-3.0. See THIRD_PARTY_NOTICES.md.
import { findModuleChild } from "@decky/ui";

const compositionHook = findModuleChild((module: unknown) => {
  if (typeof module !== "object" || module === null) return undefined;
  return Object.values(module).find((value) =>
    typeof value === "function" &&
    value.toString().includes("AddMinimumCompositionStateRequest") &&
    value.toString().includes("ChangeMinimumCompositionStateRequest") &&
    value.toString().includes("RemoveMinimumCompositionStateRequest") &&
    !value.toString().includes("m_mapCompositionStateRequests"));
}) as ((level: number) => void) | undefined;

export const compositionAvailable = typeof compositionHook === "function";

export function NotificationComposition() {
  // Notification = 1. Never request Overlay = 2, which can take game input focus.
  compositionHook!(1);
  return null;
}
