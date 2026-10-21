// Passkey ceremonies: ask the backend for options, let the browser talk to the authenticator, send the answer back.

import {
  browserSupportsWebAuthn,
  startAuthentication,
  startRegistration,
  type PublicKeyCredentialCreationOptionsJSON,
  type PublicKeyCredentialRequestOptionsJSON,
} from "@simplewebauthn/browser";

import { post } from "./api";
import type { Ceremony, PasskeyInfo } from "./types";

export const passkeysSupported = () => browserSupportsWebAuthn();

/** A readable message for a failed browser prompt, or null when the person simply closed it. */
export function promptError(err: unknown): string | null {
  const name = (err as { name?: string } | null)?.name;
  if (name === "NotAllowedError" || name === "AbortError") return null;
  if (name === "InvalidStateError") return "This device already has a passkey for Quarry.";
  if (name === "SecurityError") return "Passkeys only work on the address Quarry is set up for, over HTTPS.";
  return (err as Error)?.message || "The passkey prompt failed.";
}

/** A short default name for a new passkey, so the list says which device is which. */
export function deviceLabel(): string {
  const ua = navigator.userAgent;
  if (/Android/i.test(ua)) return "Android phone";
  if (/iPhone|iPad/i.test(ua)) return "iPhone or iPad";
  if (/Windows/i.test(ua)) return "Windows PC";
  if (/Mac OS X/i.test(ua)) return "Mac";
  if (/Linux/i.test(ua)) return "Linux PC";
  return "Passkey";
}

export async function runSetup(token: string, displayName: string, label: string): Promise<string[]> {
  const begin = await post<Ceremony<PublicKeyCredentialCreationOptionsJSON>>("/api/setup/begin", {
    token,
    display_name: displayName,
  });
  const credential = await startRegistration({ optionsJSON: begin.options });
  const done = await post<{ recovery_codes: string[] }>("/api/setup/finish", {
    challenge_id: begin.challenge_id,
    credential,
    label,
  });
  return done.recovery_codes;
}

export async function runSignIn(): Promise<void> {
  const begin = await post<Ceremony<PublicKeyCredentialRequestOptionsJSON>>("/api/auth/login/begin");
  const credential = await startAuthentication({ optionsJSON: begin.options });
  await post("/api/auth/login/finish", { challenge_id: begin.challenge_id, credential });
}

export async function runAddPasskey(label: string): Promise<PasskeyInfo> {
  const begin = await post<Ceremony<PublicKeyCredentialCreationOptionsJSON>>("/api/auth/passkeys/begin");
  const credential = await startRegistration({ optionsJSON: begin.options });
  return post<PasskeyInfo>("/api/auth/passkeys/finish", { challenge_id: begin.challenge_id, credential, label });
}
