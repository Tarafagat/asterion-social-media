export default function VideoPlayer({ src, vertical }: { src: string; vertical?: boolean }) {
  return (
    <video
      controls
      preload="metadata"
      src={src}
      style={{
        width: "100%",
        aspectRatio: vertical ? "9 / 16" : "16 / 9",
        background: "#000",
        borderRadius: "0.6rem",
        objectFit: "contain",
      }}
    />
  );
}
