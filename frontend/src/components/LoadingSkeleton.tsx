type Variant = 'rows' | 'cards' | 'chart' | 'list';

interface Props {
  rows?: number;
  variant?: Variant;
}

function Sk({ className }: { className: string }) {
  return <div className={`skeleton rounded-xl border border-white/5 ${className}`} />;
}

export default function LoadingSkeleton({ rows = 5, variant = 'rows' }: Props) {
  if (variant === 'cards') {
    return (
      <div className="grid gap-5">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <Sk key={i} className="h-28" />)}
        </div>
        <div className="grid gap-5 xl:grid-cols-2">
          <Sk className="h-64" />
          <Sk className="h-64" />
        </div>
        <Sk className="h-48" />
      </div>
    );
  }

  if (variant === 'chart') {
    return (
      <div className="grid gap-5">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <Sk key={i} className="h-24" />)}
        </div>
        <div className="grid gap-5 xl:grid-cols-2">
          <Sk className="h-72" />
          <Sk className="h-72" />
        </div>
      </div>
    );
  }

  if (variant === 'list') {
    return (
      <div className="grid gap-2.5">
        {Array.from({ length: rows }).map((_, i) => (
          <Sk key={i} className="h-16" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      {Array.from({ length: rows }).map((_, i) => (
        <Sk key={i} className="h-24" />
      ))}
    </div>
  );
}
