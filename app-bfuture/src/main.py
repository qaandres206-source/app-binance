import flet as ft
import asyncio
import os
import time
import json
from dotenv import load_dotenv
from pathlib import Path
import hmac
import hashlib
from urllib.parse import urlencode
import aiohttp

# --- Cargar archivo .env ---
# Obtener la ruta absoluta del archivo .env
env_path = Path(__file__).parent / "assets" / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_API_SECRET")


class BinanceConnector:
    """
    Clase que interactúa de forma asíncrona con Binance Futures.
    Usa la API REST real para obtener posiciones y órdenes.
    """
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://fapi.binance.com"
        
        # Validar si las claves existen
        if not api_key or not secret_key:
            print("ADVERTENCIA: Claves de API no encontradas en el entorno.")

    def _generate_signature(self, params):
        """Genera la firma HMAC-SHA256 para las peticiones."""
        query_string = urlencode(params)
        return hmac.new(
            self.secret_key.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()

    async def get_open_orders_and_positions(self):
        """
        Obtiene órdenes abiertas y posiciones reales de Binance Futures.
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Obtener posiciones abiertas
                timestamp = int(time.time() * 1000)
                params = {"timestamp": timestamp}
                signature = self._generate_signature(params)
                params["signature"] = signature
                
                headers = {
                    "X-MBX-APIKEY": self.api_key
                }
                
                # GET /fapi/v2/positionRisk - Información de posiciones
                async with session.get(
                    f"{self.base_url}/fapi/v2/positionRisk",
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        positions = await resp.json()
                        # Filtrar solo posiciones abiertas
                        open_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
                    else:
                        open_positions = []
                
                # GET /fapi/v1/openOrders - Órdenes abiertas
                async with session.get(
                    f"{self.base_url}/fapi/v1/openOrders",
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        orders = await resp.json()
                    else:
                        orders = []
                
                return orders, open_positions
                
        except Exception as e:
            print(f"Error al obtener datos de Binance: {e}")
            # Retornar datos simulados en caso de error
            return [], []

    async def place_scalping_order(self, symbol, quantity):
        """Simula la colocación de la orden principal de la estrategia ($10 USDT)."""
        await asyncio.sleep(2)
        return {"status": "FILLED", "orderId": int(time.time()), "symbol": symbol, "quantity": quantity}
    
    async def cancel_order(self, order_id):
        """Simula la cancelación de una orden."""
        await asyncio.sleep(1)
        return {"status": "CANCELED", "id": order_id}

# --- 2. INTERFAZ DE USUARIO (FLET) ---

class TradingBotUI(ft.Column):
    def __init__(self, page: ft.Page, connector: BinanceConnector):
        # Es fundamental que el control raíz expanda para ocupar toda la pantalla, especialmente en móvil.
        super().__init__(expand=True) 
        self.page = page
        self.connector = connector
        self.is_running = False
        self.monitoring_task = None
        
        # Referencias de Controles
        self.status_text = ft.Text("ESTADO: Detenido", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_ACCENT_700)
        self.symbol_text = ft.Text("", weight=ft.FontWeight.BOLD, size=18, color=ft.Colors.WHITE)
        self.size_text = ft.Text("", size=13, color=ft.Colors.GREY_400)
        self.entry_price_text = ft.Text("", size=13, color=ft.Colors.GREY_400)
        self.mark_price_text = ft.Text("", size=13, color=ft.Colors.GREY_400)
        self.liq_price_text = ft.Text("", size=13, color=ft.Colors.GREY_400)
        self.margin_ratio_text = ft.Text("", size=13, color=ft.Colors.GREY_400)
        self.pnl_text = ft.Text("PnL: $0.00", weight=ft.FontWeight.BOLD, size=16)
        self.pnl_pct_text = ft.Text("", size=12, color=ft.Colors.GREY_400)
        self.open_orders_list = ft.ListView(
            spacing=10,
            expand=True,
            auto_scroll=False
        )
        
        # Botón de Control (Adaptive=True para estilo iOS) [2-4]
        self.run_switch = ft.Switch(
            label="Ejecutar Monitoreo Automático",
            value=self.is_running,
            on_change=self.toggle_bot_state,
            adaptive=True 
        )
        
        # Botón para Iniciar un trade (CupertinoFilledButton para estilo iOS) [18]
        self.start_trade_btn = ft.CupertinoFilledButton(
            content=ft.Text("INICIAR SCALPING ($10 USDT)"),
            on_click=self.start_scalping_trade,
            disabled=True 
        )
        
        # Pestañas
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            expand=True, # Permitir que las pestañas usen el espacio restante
            tabs=[
                ft.Tab(
                    text="Dashboard",
                    icon=ft.Icons.DASHBOARD_ROUNDED,
                    content=ft.Container(
                        content=ft.Column([
                            self.status_text,
                            ft.Divider(height=10),
                            # Símbolo
                            self.symbol_text,
                            ft.Container(height=10),
                            # Detalles de la posición en grid
                            ft.Column([
                                ft.Row([
                                    ft.Column([
                                        ft.Text("Tamaño", size=11, color=ft.Colors.GREY_400),
                                        self.size_text,
                                    ], tight=True, spacing=3),
                                    ft.Column([
                                        ft.Text("Entrada", size=11, color=ft.Colors.GREY_400),
                                        self.entry_price_text,
                                    ], tight=True, spacing=3),
                                    ft.Column([
                                        ft.Text("Marca", size=11, color=ft.Colors.GREY_400),
                                        self.mark_price_text,
                                    ], tight=True, spacing=3),
                                ], spacing=20, expand=True),
                                ft.Row([
                                    ft.Column([
                                        ft.Text("Liquidación", size=11, color=ft.Colors.GREY_400),
                                        self.liq_price_text,
                                    ], tight=True, spacing=3),
                                    ft.Column([
                                        ft.Text("Margen %", size=11, color=ft.Colors.GREY_400),
                                        self.margin_ratio_text,
                                    ], tight=True, spacing=3),
                                ], spacing=20, expand=True),
                            ], spacing=12),
                            ft.Divider(height=10),
                            # PnL
                            ft.Row([
                                ft.Column([self.pnl_text, self.pnl_pct_text], tight=True, spacing=2),
                            ], spacing=10),
                            ft.Container(height=20),
                            ft.Container(
                                content=self.start_trade_btn,
                                alignment=ft.alignment.center
                            )
                        ], horizontal_alignment=ft.CrossAxisAlignment.START, spacing=5),
                        padding=20
                    )
                ),
                ft.Tab(
                    text="Órdenes Abiertas",
                    icon=ft.Icons.LIST_ALT_ROUNDED,
                    content=ft.Container(
                        content=self.open_orders_list, 
                        expand=True, 
                        padding=10
                    )
                ),
            ],
        )

        # Controles principales de la interfaz
        self.controls = [
            ft.Container(
                content=ft.Text(
                    "Bot de Trading de Futuros",
                    size=24,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.PRIMARY
                ),
                padding=15,
                alignment=ft.alignment.center
            ),
            ft.Divider(height=1),
            ft.Container(
                content=ft.Row([self.run_switch], alignment=ft.MainAxisAlignment.CENTER),
                padding=10
            ),
            ft.Container(
                content=self.tabs,
                expand=True
            )
        ]

    # --- LÓGICA DE CONTROL ---

    def toggle_bot_state(self, e):
        """Maneja el evento de Play/Pause."""
        self.is_running = e.control.value
        
        if self.is_running:
            self.status_text.value = "ESTADO: Ejecutando Monitoreo..."
            self.status_text.color = ft.Colors.GREEN_ACCENT_700
            self.start_trade_btn.disabled = False
            
            # CRÍTICO: Iniciar la tarea asíncrona de fondo [1]
            self.monitoring_task = self.page.run_task(self.run_auto_monitoring_loop)
            
        else:
            self.status_text.value = "ESTADO: Detenido"
            self.status_text.color = ft.Colors.RED_ACCENT_700
            self.start_trade_btn.disabled = True
            
            # Cancelar la tarea de fondo al detener el bot
            if self.monitoring_task:
                self.monitoring_task.cancel()
        
        self.page.update()

    async def run_auto_monitoring_loop(self):
        """Bucle que se ejecuta en segundo plano (run_task) para actualizar la UI."""
        while self.is_running:
            try:
                # La llamada al conector debe ser 'await' porque es asíncrona
                await self.fetch_and_display_orders()
            except asyncio.CancelledError:
                # Importante: manejo de la cancelación
                print("Tarea de monitoreo cancelada limpiamente.")
                break
            except Exception as e:
                # Si hay un error de conexión, lo mostramos sin congelar la UI
                self.status_text.value = f"ERROR DE MONITOREO: {e.__class__.__name__}"
                self.page.update()
            
            # Esperamos 5 segundos antes de la próxima actualización [1]
            await asyncio.sleep(5) 

    async def fetch_and_display_orders(self):
        """Función que obtiene datos de Binance y actualiza la UI."""
        
        orders, positions = await self.connector.get_open_orders_and_positions()
        
        # --- 1. Actualizar Dashboard ---
        if positions:
            pos = positions[0]  # Tomamos la primera posición
            pnl_val = float(pos.get('unRealizedProfit', 0.0))
            pnl_color = ft.Colors.GREEN if pnl_val >= 0 else ft.Colors.RED
            
            symbol = pos.get('symbol', 'N/A')
            position_amt = float(pos.get('positionAmt', 0))
            entry_price = float(pos.get('entryPrice', 0))
            mark_price = float(pos.get('markPrice', 0))
            liq_price = float(pos.get('liquidationPrice', 0))
            margin_ratio = float(pos.get('marginRatio', 0))
            
            # Calcular porcentaje de PnL
            if entry_price > 0:
                pnl_pct = (pnl_val / (abs(position_amt) * entry_price)) * 100
            else:
                pnl_pct = 0
            
            # Actualizar valores
            self.symbol_text.value = symbol
            self.size_text.value = f"{position_amt:.4f}"
            self.entry_price_text.value = f"${entry_price:.5f}"
            self.mark_price_text.value = f"${mark_price:.5f}"
            self.liq_price_text.value = f"${liq_price:.5f}"
            self.margin_ratio_text.value = f"{margin_ratio*100:.2f}%"
            
            self.pnl_text.value = f"PnL: ${pnl_val:.2f}"
            self.pnl_text.color = pnl_color
            self.pnl_pct_text.value = f"({pnl_pct:.2f}%)"
            self.pnl_pct_text.color = pnl_color
        else:
            self.symbol_text.value = "Sin posiciones"
            self.size_text.value = "—"
            self.entry_price_text.value = "—"
            self.mark_price_text.value = "—"
            self.liq_price_text.value = "—"
            self.margin_ratio_text.value = "—"
            self.pnl_text.value = "PnL: $0.00"
            self.pnl_text.color = ft.Colors.GREY_400
            self.pnl_pct_text.value = "(0.00%)"
            self.pnl_pct_text.color = ft.Colors.GREY_400
        
        # --- 2. Actualizar Lista de Órdenes ---
        new_controls = []
        if not orders:
            new_controls.append(ft.Text("No hay órdenes abiertas actualmente.", italic=True, color="#707070"))
        else:
            for order in orders:
                symbol = order.get('symbol', 'N/A')
                side = order.get('side', 'N/A')
                order_type = order.get('type', 'N/A')
                price = order.get('price', 'N/A')
                qty = order.get('origQty', order.get('qty', 'N/A'))
                order_id = order.get('orderId', order.get('id', 'N/A'))
                
                # Color según lado de la orden
                side_color = "#4CAF50" if side == "BUY" else "#FF6B6B"
                
                new_controls.append(
                    ft.CupertinoListTile( 
                        title=ft.Text(f"[{order_type}] {symbol}", weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                        subtitle=ft.Text(f"{side} | Cantidad: {qty} @ {price}", color="#B0B0B0"),
                        trailing=ft.TextButton(
                            "CANCELAR", 
                            icon=ft.Icons.CANCEL_OUTLINED, 
                            icon_color="#FF6B6B",
                            on_click=self.handle_cancel_order,
                            data=order_id 
                        ),
                        bgcolor="#2A2A2A",
                    )
                )

        self.open_orders_list.controls.clear()
        self.open_orders_list.controls.extend(new_controls)
        
        # CRÍTICO: Refrescar la UI desde el hilo de fondo
        self.page.update()

    async def start_scalping_trade(self, e):
        """Ejecuta el trade de scalping (Trade Action)"""
        if not self.is_running:
            self.page.snack_bar = ft.SnackBar(ft.Text("Debe iniciar el bot primero (Play)."), open=True)
            self.page.update()
            return
            
        self.start_trade_btn.disabled = True
        self.start_trade_btn.content = ft.Text("Operando...", color=ft.Colors.WHITE)
        self.page.update()
        
        try:
            # Colocamos la orden ($10 USDT -> 0.001 BTC aprox.)
            result = await self.connector.place_scalping_order(symbol="BTCUSDT", quantity=0.001)
            
            # Mostrar confirmación [23]
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Orden {result['status']} ID: {result['orderId']}"), open=True)
            
        except Exception as api_error:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"FALLO DE ÓRDEN: {api_error}"), open=True)
            
        finally:
            # Revertir el estado del botón y forzar una actualización del monitoreo
            self.start_trade_btn.disabled = False
            self.start_trade_btn.content = ft.Text("INICIAR SCALPING ($10 USDT)")
            await self.fetch_and_display_orders()
            self.page.update()


    async def handle_cancel_order(self, e):
        """Maneja la cancelación de una orden a través del botón."""
        order_id = e.control.data
        e.control.disabled = True # Deshabilitar el botón mientras se procesa
        self.page.update()
        
        try:
            # Llamada asíncrona a la API de cancelación [16, 17]
            result = await self.connector.cancel_order(order_id)
            if result.get("status") == "CANCELED":
                msg = f"Orden {order_id} cancelada."
            else:
                msg = f"Fallo al cancelar {order_id}."
            
            self.page.snack_bar = ft.SnackBar(ft.Text(msg), open=True)
            
        except Exception as api_error:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Error al cancelar: {api_error}"), open=True)
            e.control.disabled = False # Reactivar si falla

        finally:
            # Forzar la actualización de la lista de órdenes
            await self.fetch_and_display_orders()
            self.page.update()


async def main(page: ft.Page):
    # --- CONFIGURACIÓN DE LA PÁGINA ---
    page.title = "Bot Flet Futuros"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.theme_mode = ft.ThemeMode.DARK # Opcional, pero da mejor contraste
    page.adaptive = True  # ¡CRÍTICO para estilo iOS! [4]
    page.padding = 0

    # Inicializar el conector
    connector = BinanceConnector(API_KEY, SECRET_KEY)
    
    # Crear e iniciar la interfaz
    app = TradingBotUI(page, connector)
    
    page.add(
        ft.SafeArea( # Asegura que la UI no se solape con la barra de estado de iOS [24]
            ft.Container(
                content=app,
                expand=True
            )
        )
    )

if __name__ == "__main__":
    ft.app(target=main)