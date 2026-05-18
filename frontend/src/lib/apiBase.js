export function inferApiBaseFromHost(hostname) {
  const host = (hostname || "").toLowerCase();

  const isProdFrontendHost =
    host === "rex.papadrew.com" ||
    host === "www.rex.papadrew.com" ||
    host === "rex-os.vercel.app" ||
    /^rex-os-git-.*\.vercel\.app$/i.test(host);

  if (isProdFrontendHost) {
    return "https://rex-os-api-production.up.railway.app";
  }

  if (host === "rex-os-demo.vercel.app" || /^rex-os-demo-git-.*\.vercel\.app$/i.test(host)) {
    return "https://rex-os-demo.up.railway.app";
  }

  return "";
}

export function inferApiBaseFromWindow() {
  if (typeof window === "undefined") return "";
  return inferApiBaseFromHost(window.location.hostname);
}
