import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { Analisis, SolicitudesService } from './solicitudes.service';

/** Un solo estado a la vez: no puede haber "cargando" y "error" al mismo tiempo. */
type Estado =
  | { tipo: 'inicial' }
  | { tipo: 'cargando' }
  | { tipo: 'error'; mensaje: string }
  | { tipo: 'listo'; analisis: Analisis };

@Component({
  selector: 'app-analizar-solicitud',
  standalone: true,
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form [formGroup]="formulario" (ngSubmit)="analizar()">
      <label>Id de la solicitud <input formControlName="id" /></label>
      <label>Id del cliente <input formControlName="cliente_id" /></label>
      <label>Texto <textarea formControlName="texto" rows="5"></textarea></label>
      <button type="submit" [disabled]="formulario.invalid || estado().tipo === 'cargando'">
        Analizar
      </button>
    </form>

    @switch (estado().tipo) {
      @case ('cargando') {
        <p role="status">Analizando la solicitud…</p>
      }
      @case ('error') {
        <p role="alert">{{ mensajeDeError() }}</p>
      }
      @case ('listo') {
        @if (analisis(); as a) {
          <section aria-live="polite">
            <h2>Resultado</h2>
            <p>Categoría: {{ a.categoria }} · Prioridad: {{ a.prioridad }}</p>
            @if (a.consulta_cliente === 'fallida') {
              <p>No fue posible consultar los datos del cliente.</p>
            }
            <p>{{ a.respuesta_sugerida }}</p>
            <small>
              Tokens: {{ a.tokens_entrada }} de entrada, {{ a.tokens_salida }} de salida
              @if (a.tokens_estimados) { (estimados) }
              · Costo: USD {{ a.costo_estimado_usd }}
            </small>
          </section>
        }
      }
    }
  `,
})
export class AnalizarSolicitudComponent {
  private readonly servicio = inject(SolicitudesService);
  private readonly destroyRef = inject(DestroyRef);

  readonly formulario = inject(FormBuilder).nonNullable.group({
    id: ['', Validators.required],
    cliente_id: ['', Validators.required],
    texto: ['', Validators.required],
  });

  readonly estado = signal<Estado>({ tipo: 'inicial' });

  analisis(): Analisis | null {
    const estado = this.estado();
    return estado.tipo === 'listo' ? estado.analisis : null;
  }

  mensajeDeError(): string {
    const estado = this.estado();
    return estado.tipo === 'error' ? estado.mensaje : '';
  }

  analizar(): void {
    if (this.formulario.invalid || this.estado().tipo === 'cargando') {
      return;
    }
    this.estado.set({ tipo: 'cargando' });

    this.servicio
      .analizar(this.formulario.getRawValue())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (analisis) => this.estado.set({ tipo: 'listo', analisis }),
        error: (error: HttpErrorResponse) =>
          this.estado.set({ tipo: 'error', mensaje: this.describir(error) }),
      });
  }

  private describir(error: HttpErrorResponse): string {
    switch (error.status) {
      case 0:
        return 'No hay conexión con el servicio.';
      case 409:
        return 'Ya existe un análisis para ese id.';
      case 422:
        return 'Los datos de la solicitud no son válidos.';
      case 502:
        return 'No fue posible analizar la solicitud. Intente de nuevo.';
      default:
        return 'Ocurrió un error inesperado.';
    }
  }
}
