import { HttpClient } from '@angular/common/http';
import { Injectable, InjectionToken, inject } from '@angular/core';
import { Observable } from 'rxjs';

export interface SolicitudEntrada {
  id: string;
  texto: string;
  cliente_id: string;
}

export interface Analisis {
  id: string;
  cliente_id: string;
  estado: 'pendiente' | 'completado' | 'fallido';
  categoria: 'facturacion' | 'tecnico' | 'comercial' | 'otro' | null;
  prioridad: 'alta' | 'media' | 'baja' | null;
  consulta_cliente: 'no_requerida' | 'ok' | 'fallida';
  info_cliente: Record<string, unknown> | null;
  respuesta_sugerida: string | null;
  tokens_entrada: number;
  tokens_salida: number;
  tokens_estimados: boolean;
  costo_estimado_usd: string;
  creado_en: string;
}

/** URL base de la API. Cada ambiente la provee en la configuración de la aplicación. */
export const API_URL = new InjectionToken<string>('API_URL', {
  providedIn: 'root',
  factory: () => '',
});

@Injectable({ providedIn: 'root' })
export class SolicitudesService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = inject(API_URL);

  analizar(solicitud: SolicitudEntrada): Observable<Analisis> {
    return this.http.post<Analisis>(`${this.apiUrl}/solicitudes/analizar`, solicitud);
  }
}
