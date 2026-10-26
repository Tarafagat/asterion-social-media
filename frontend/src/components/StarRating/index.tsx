export default function StarRating({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (rating: number | null) => void;
}) {
  return (
    <div style={{ display: "flex", gap: "0.15rem" }} onClick={(e) => e.preventDefault()}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          title={`Calificar con ${n} estrella${n > 1 ? "s" : ""}`}
          onClick={() => onChange(value === n ? null : n)}
          style={{
            background: "none",
            border: "none",
            padding: 0,
            fontSize: "1.05rem",
            lineHeight: 1,
            color: value !== null && n <= value ? "var(--color-asterion-gold)" : "rgba(255,255,255,0.25)",
          }}
        >
          ★
        </button>
      ))}
    </div>
  );
}
