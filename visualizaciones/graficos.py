import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import customtkinter as ctk


def crear_grafico_ventas(parent, datos_ventas):
    """Crea un gráfico de líneas para las ventas (pedidos no cancelados) de los últimos 7 días."""
    fig, ax = plt.subplots(figsize=(5, 3), dpi=100)
    plt.close(fig)  # el canvas de Tk ya retiene la figura; evita que pyplot la acumule en memoria
    fig.patch.set_facecolor('#12261d')
    ax.set_facecolor('#12261d')

    dias = [d['dia'] for d in datos_ventas]
    totales = [d['total'] for d in datos_ventas]

    ax.plot(dias, totales, marker='o', color='#10b981', linewidth=2, markersize=6)
    ax.fill_between(dias, totales, color='#10b981', alpha=0.2)

    ax.set_title("Ventas últimos 7 días", color='white', fontsize=10, pad=10)
    ax.tick_params(axis='x', colors='white', labelsize=8)
    ax.tick_params(axis='y', colors='white', labelsize=8)
    for spine in ax.spines.values():
        spine.set_color('#2d4a3d')

    plt.tight_layout()

    canvas = FigureCanvasTkAgg(fig, master=parent)
    return canvas.get_tk_widget()


def crear_grafico_categorias(parent, datos_cat):
    """Crea un gráfico de barras para las ventas por categoría de producto."""
    fig, ax = plt.subplots(figsize=(5, 3), dpi=100)
    plt.close(fig)  # el canvas de Tk ya retiene la figura; evita que pyplot la acumule en memoria
    fig.patch.set_facecolor('#12261d')
    ax.set_facecolor('#12261d')

    categorias = [c['categoria'] for c in datos_cat]
    totales = [c['total'] for c in datos_cat]

    colores = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4']
    ax.bar(categorias, totales, color=colores[:len(categorias)] or ['#10b981'])

    ax.set_title("Ventas por Categoría", color='white', fontsize=10, pad=10)
    ax.tick_params(axis='x', colors='white', labelsize=8, rotation=15)
    ax.tick_params(axis='y', colors='white', labelsize=8)
    for spine in ax.spines.values():
        spine.set_color('#2d4a3d')

    plt.tight_layout()

    canvas = FigureCanvasTkAgg(fig, master=parent)
    return canvas.get_tk_widget()
