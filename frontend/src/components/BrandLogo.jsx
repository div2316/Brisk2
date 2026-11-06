export default function BrandLogo({ size = 40, text = true, className = "" }) {
  return (
    <span className={`inline-flex items-center gap-3 ${className}`}>
      <img src="/brisk2-logo.jpg" alt="BRISK2 logo" width={size} height={size}
        className="rounded-xl object-cover" style={{ width: size, height: size }} />
      {text && <span className="text-xl font-semibold tracking-tight text-white">BRISK<span className="text-violet-400">2</span></span>}
    </span>
  );
}
