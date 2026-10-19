/**
 * Open a pre-signed URL (10 minutes, contract §6/§7) in a new tab. The tab is opened synchronously in the
 * click handler (so popup blockers allow it) and pointed at the URL once the API returns it; when the
 * browser refuses the tab, the URL is returned so the page can show a plain link instead.
 */
export async function openPresigned(getUrl: () => Promise<{ url: string }>): Promise<string | null> {
  let tab: Window | null;
  try {
    tab = window.open("about:blank", "_blank");
  } catch {
    tab = null;
  }
  try {
    const { url } = await getUrl();
    if (tab) {
      tab.opener = null;
      tab.location.href = url;
      return null;
    }
    return url;
  } catch (e) {
    tab?.close();
    throw e;
  }
}
