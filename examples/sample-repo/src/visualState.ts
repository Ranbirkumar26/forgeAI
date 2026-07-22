export function getBannerTone(status: "idle" | "running" | "failed") {
  if (status === "running") return "teal";
  if (status === "failed") return "ruby";
  return "neutral";
}

