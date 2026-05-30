import { Shield } from 'lucide-react';

type Props = {
  title: string;
  description?: string;
  icon?: React.ReactNode;
};

export default function EmptyState({ title, description, icon }: Props) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-700/30 bg-slate-900/20 px-6 py-12 text-center">
      <div className="mb-4 grid h-14 w-14 place-items-center rounded-2xl border border-cyan-400/15 bg-cyan-400/8 text-cyan-400/60">
        {icon ?? <Shield size={26} strokeWidth={1.5} />}
      </div>
      <h3 className="text-sm font-semibold text-slate-300">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-xs text-[12px] leading-5 text-slate-500">{description}</p>
      )}
    </div>
  );
}
