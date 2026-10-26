export default function VideoPlayer({ src, vertical }: { src: string; vertical?: boolean }) {
  return (
    <div
      style={{
        width: "100%",
        maxWidth: vertical ? "20rem" : "none",
        margin: vertical ? "0 auto" : undefined,
        padding: vertical ? "0.5rem" : 0,
        background: vertical ? "#000" : "transparent",
        borderRadius: vertical ? "1.6rem" : "0.6rem",
        border: vertical ? "1px solid rgba(255,255,255,0.15)" : "none",
        boxShadow: vertical ? "0 12px 30px rgba(0,0,0,0.45)" : "none",
      }}
    >
      <video
        controls
        preload="metadata"
        src={src}
        style={{
          display: "block",
          width: "100%",
          aspectRatio: vertical ? "9 / 16" : "16 / 9",
          background: "#000",
          borderRadius: vertical ? "1.1rem" : "0.6rem",
          objectFit: "contain",
        }}
      />
    </div>
  );
}
