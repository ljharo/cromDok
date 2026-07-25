import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Check, Copy, KeyRound, MoreHorizontal, Trash2 } from "lucide-react";

import { useCreateApiKey, useRevokeApiKey, useApiKeys } from "@/features/api-keys/hooks";
import {
  API_KEY_SCOPES,
  apiKeyCreateSchema,
  type ApiKey,
  type ApiKeyCreate,
  type ApiKeyCreated,
  type ApiKeyScope,
} from "@/types/api-key";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const SCOPE_LABELS: Record<ApiKeyScope, string> = {
  "runners:read": "Lectura de runners",
  "runners:execute": "Ejecutar runners",
  admin: "Administrador",
};

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString("es") : "Nunca";
}

/** Admin-only API key management: list, create (shows the token once) and revoke. */
export default function ApiKeysPage() {
  const { data: apiKeys, isPending, isError } = useApiKeys();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">API Keys</h1>
          <p className="text-muted-foreground">
            Credenciales para integraciones externas (spec 9.4.2).
          </p>
        </div>
        <CreateApiKeyDialog />
      </div>

      {isPending && <p className="text-muted-foreground">Cargando API keys…</p>}
      {isError && <p className="text-destructive">No se pudieron cargar las API keys.</p>}
      {apiKeys && apiKeys.length === 0 && (
        <p className="text-muted-foreground">No hay API keys creadas.</p>
      )}
      {apiKeys && apiKeys.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Scopes</TableHead>
              <TableHead>Creada</TableHead>
              <TableHead>Último uso</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {apiKeys.map((apiKey) => (
              <ApiKeyRow key={apiKey.id} apiKey={apiKey} />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function ApiKeyRow({ apiKey }: { apiKey: ApiKey }) {
  const [revokeOpen, setRevokeOpen] = useState(false);
  const revokeApiKey = useRevokeApiKey();

  return (
    <TableRow>
      <TableCell className="font-medium">{apiKey.name}</TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {apiKey.scopes.map((scope) => (
            <Badge key={scope} variant="secondary">
              {SCOPE_LABELS[scope]}
            </Badge>
          ))}
        </div>
      </TableCell>
      <TableCell>{formatDate(apiKey.created_at)}</TableCell>
      <TableCell>{formatDate(apiKey.last_used_at)}</TableCell>
      <TableCell>
        <Badge variant={apiKey.revoked ? "secondary" : "default"}>
          {apiKey.revoked ? "Revocada" : "Activa"}
        </Badge>
      </TableCell>
      <TableCell>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label={`Acciones de ${apiKey.name}`}>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onSelect={() => setRevokeOpen(true)}
              disabled={apiKey.revoked}
              className="text-destructive focus:text-destructive"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Revocar
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Dialog open={revokeOpen} onOpenChange={setRevokeOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Revocar API key</DialogTitle>
              <DialogDescription>
                ¿Seguro que quieres revocar {apiKey.name}? La revocación es inmediata y no se puede
                deshacer.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setRevokeOpen(false)}>
                Cancelar
              </Button>
              <Button
                variant="destructive"
                disabled={revokeApiKey.isPending}
                onClick={() =>
                  revokeApiKey.mutate(apiKey.id, { onSuccess: () => setRevokeOpen(false) })
                }
              >
                {revokeApiKey.isPending ? "Revocando…" : "Revocar"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </TableCell>
    </TableRow>
  );
}

function CreateApiKeyDialog() {
  const [open, setOpen] = useState(false);
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const createApiKey = useCreateApiKey();

  const form = useForm<ApiKeyCreate>({
    resolver: zodResolver(apiKeyCreateSchema),
    defaultValues: { name: "", scopes: [] },
  });

  const onSubmit = (values: ApiKeyCreate) => {
    createApiKey.mutate(values, {
      onSuccess: (apiKey) => setCreated(apiKey),
    });
  };

  const close = () => {
    setOpen(false);
    setCreated(null);
    form.reset();
  };

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? setOpen(true) : close())}>
      <DialogTrigger asChild>
        <Button>
          <KeyRound className="mr-2 h-4 w-4" />
          Nueva API key
        </Button>
      </DialogTrigger>
      <DialogContent>
        {created ? (
          <>
            <DialogHeader>
              <DialogTitle>API key creada</DialogTitle>
              <DialogDescription>
                Este token no se volverá a mostrar. Cópialo ahora y guárdalo en un lugar seguro.
              </DialogDescription>
            </DialogHeader>
            <TokenDisplay token={created.token} />
            <DialogFooter>
              <Button onClick={close}>Listo</Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Nueva API key</DialogTitle>
              <DialogDescription>
                Selecciona un nombre descriptivo y los scopes que necesita.
              </DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Nombre</FormLabel>
                      <FormControl>
                        <Input autoComplete="off" placeholder="ci-pipeline" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="scopes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Scopes</FormLabel>
                      <div className="space-y-2">
                        {API_KEY_SCOPES.map((scope) => (
                          <label key={scope} className="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              className="size-4 accent-primary"
                              checked={field.value.includes(scope)}
                              onChange={(event) => {
                                field.onChange(
                                  event.target.checked
                                    ? [...field.value, scope]
                                    : field.value.filter((s: ApiKeyScope) => s !== scope),
                                );
                              }}
                            />
                            {SCOPE_LABELS[scope]}
                          </label>
                        ))}
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <DialogFooter>
                  <Button type="submit" disabled={createApiKey.isPending}>
                    {createApiKey.isPending ? "Creando…" : "Crear API key"}
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function TokenDisplay({ token }: { token: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex items-center gap-2 rounded-md border bg-muted/40 p-3">
      <code className="flex-1 break-all font-mono text-sm">{token}</code>
      <Button type="button" variant="outline" size="icon" aria-label="Copiar token" onClick={copy}>
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </Button>
    </div>
  );
}
