import { Database, Brain, BarChart3, Sparkles } from 'lucide-react';

const FEATURES = [
  { icon: Database, title: 'Real billing data', text: 'Every number comes from AWS Cost Explorer, Azure Cost Management, the GCP billing export or the DigitalOcean API.' },
  { icon: Brain, title: 'Remembers the conversation', text: 'Four memory layers keep long sessions coherent and compress old turns automatically.' },
  { icon: BarChart3, title: 'Charts and savings', text: 'Breakdowns, trends, forecasts and concrete optimization recommendations you can copy anywhere.' },
];

export default function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-full text-center px-4 py-8">
      <div className="brand-gradient size-14 rounded-2xl flex items-center justify-center mb-5 shadow-glow">
        <Sparkles className="w-7 h-7 text-white" />
      </div>
      <h2 className="text-2xl font-semibold tracking-tight text-slate-50 mb-2">
        Ask your cloud bill <span className="text-gradient">anything</span>
      </h2>
      <p className="text-sm text-slate-400 max-w-lg">
        Shimo analyses spend across AWS, Azure, GCP and DigitalOcean in plain English. Pick your providers above, then ask a question or try a suggestion below.
      </p>
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-3xl">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <div key={title} className="glass rounded-2xl p-4 text-left">
            <Icon className="w-5 h-5 text-primary-400 mb-2" />
            <p className="text-sm font-semibold text-slate-100">{title}</p>
            <p className="mt-1 text-xs text-slate-400 leading-relaxed">{text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
