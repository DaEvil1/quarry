// What another app shared into Quarry (Android share sheet → the manifest's share_target → /share?title&text&url),
// turned into the text of a capture.

export function sharedText(params: { title?: string | null; text?: string | null; url?: string | null }): string {
  const title = params.title?.trim() ?? "";
  let text = params.text?.trim() ?? "";
  const url = params.url?.trim() ?? "";
  const parts: string[] = [];
  // apps often send the page title as the text too, or put the link inside the text
  if (title && !text.startsWith(title)) parts.push(title);
  if (text) parts.push(text);
  if (url && !text.includes(url)) parts.push(url);
  text = parts.join("\n\n");
  return text;
}
