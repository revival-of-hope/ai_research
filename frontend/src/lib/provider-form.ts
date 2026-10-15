import type { Provider, ProviderCatalogEntry, ProviderType } from "@/lib/types";

export type ProviderFormState = {
  name: string;
  model: string;
  baseUrl: string;
  providerType: ProviderType;
};

export function providerForm(provider?: Provider): ProviderFormState {
  return {
    name: provider?.name ?? "",
    model: provider?.model ?? "",
    baseUrl: provider?.base_url ?? "",
    providerType: provider?.provider_type ?? "custom",
  };
}

export function selectProviderTemplate(current: ProviderFormState, entry: ProviderCatalogEntry, catalog: ProviderCatalogEntry[]): ProviderFormState {
  const previous = catalog.find((item) => item.id === current.providerType);
  return {
    ...current,
    name: !current.name || current.name === previous?.name ? (entry.id === "custom" ? "" : entry.name) : current.name,
    model: entry.models[0] ?? "",
    baseUrl: entry.base_url,
    providerType: entry.id,
  };
}

export function providerModelsRequest(form: ProviderFormState, apiKey: string, providerId?: number) {
  return {
    provider_type: form.providerType,
    base_url: form.baseUrl.trim(),
    api_key: apiKey.trim() || null,
    provider_id: providerId ?? null,
  };
}

export function providerSaveRequest(form: ProviderFormState, apiKey: string) {
  return {
    name: form.name.trim(),
    model: form.model.trim(),
    base_url: form.baseUrl.trim(),
    provider_type: form.providerType,
    api_key: apiKey.trim() || null,
  };
}

export function providerEndpoint(form: ProviderFormState): string {
  return form.baseUrl.trim().replace(/\/+$/, "") + "/responses";
}
