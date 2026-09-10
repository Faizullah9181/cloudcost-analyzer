import type { CloudProvider, ConnectionContext, ProviderStatus } from '../types';

export interface SessionSetupState {
  name: string;
  providers: CloudProvider[];
  llm: string;
  context: ConnectionContext;
}

interface SessionSetupProps {
  value: SessionSetupState;
  onChange: (next: SessionSetupState) => void;
  providerStatus: ProviderStatus[];
  llmProviders: string[];
  disabled?: boolean;
}

const PROVIDER_LABEL: Record<CloudProvider, string> = {
  aws: 'AWS',
  azure: 'Azure',
  gcp: 'GCP',
  digitalocean: 'DigitalOcean',
};

const CONTEXT_FIELD: Record<CloudProvider, { key: string; label: string; placeholder: string } | null> = {
  aws: { key: 'account_id', label: 'AWS account ID', placeholder: '123456789012' },
  azure: { key: 'subscription_id', label: 'Azure subscription ID', placeholder: '00000000-0000-…' },
  gcp: { key: 'project_id', label: 'GCP project ID', placeholder: 'my-project' },
  digitalocean: null,
};

const ALL_PROVIDERS: CloudProvider[] = ['aws', 'azure', 'gcp', 'digitalocean'];

const inputClass =
  'bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50';

export default function SessionSetup({ value, onChange, providerStatus, llmProviders, disabled }: SessionSetupProps) {
  const statusFor = (name: CloudProvider) => providerStatus.find((p) => p.name === name);

  const toggleProvider = (name: CloudProvider) => {
    const providers = value.providers.includes(name)
      ? value.providers.filter((p) => p !== name)
      : [...value.providers, name];
    onChange({ ...value, providers });
  };

  const setContext = (provider: CloudProvider, key: string, fieldValue: string) => {
    const current = value.context[provider] ?? {};
    onChange({ ...value, context: { ...value.context, [provider]: { ...current, [key]: fieldValue } } });
  };

  return (
    <section className="rounded-2xl border border-primary-500/40 bg-slate-950/90 shadow-lg shadow-primary-900/20 backdrop-blur px-4 py-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h2 className="text-base font-semibold text-slate-100">New session</h2>
        <span className="text-xs text-primary-300">Pick the clouds to analyse, then ask a question</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-slate-400">Session name</span>
          <input
            type="text"
            value={value.name}
            disabled={disabled}
            onChange={(e) => onChange({ ...value, name: e.target.value })}
            placeholder="e.g. Q3 cost review"
            className={inputClass}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-slate-400">LLM provider</span>
          <select
            value={value.llm}
            disabled={disabled}
            onChange={(e) => onChange({ ...value, llm: e.target.value })}
            className={inputClass}
          >
            {llmProviders.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-3">
        <span className="text-xs text-slate-400">Cloud providers</span>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {ALL_PROVIDERS.map((name) => {
            const checked = value.providers.includes(name);
            const configured = statusFor(name)?.configured ?? false;
            return (
              <button
                type="button"
                key={name}
                disabled={disabled}
                onClick={() => toggleProvider(name)}
                className={`inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm transition-colors disabled:opacity-50 ${
                  checked
                    ? 'border-primary-500 bg-primary-600/20 text-primary-100'
                    : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500'
                }`}
                aria-pressed={checked}
              >
                {PROVIDER_LABEL[name]}
                <span
                  className={`size-1.5 rounded-full ${configured ? 'bg-emerald-400' : 'bg-slate-600'}`}
                  title={configured ? 'Credentials configured on the backend' : 'No credentials configured'}
                />
              </button>
            );
          })}
        </div>
      </div>

      {value.providers.some((p) => CONTEXT_FIELD[p]) && (
        <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
          {value.providers.map((provider) => {
            const field = CONTEXT_FIELD[provider];
            if (!field) return null;
            return (
              <label key={provider} className="flex flex-col gap-1.5">
                <span className="text-xs text-slate-400">{field.label} <span className="text-slate-600">(optional)</span></span>
                <input
                  type="text"
                  disabled={disabled}
                  value={value.context[provider]?.[field.key] ?? ''}
                  onChange={(e) => setContext(provider, field.key, e.target.value)}
                  placeholder={field.placeholder}
                  className={inputClass}
                />
              </label>
            );
          })}
        </div>
      )}
    </section>
  );
}
