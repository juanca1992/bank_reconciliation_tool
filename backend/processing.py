# backend/processing.py

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Tuple, List
# Importar unidecode para quitar tildes/acentos
try:
    from unidecode import unidecode
except ImportError:
    print("Error: La librería 'unidecode' no está instalada.")
    print("Por favor, instálala ejecutando: pip install unidecode")
    # Alternativa simple (puede no cubrir todos los casos):
    def unidecode(text):
        import unicodedata
        return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    print("Usando alternativa simple para quitar acentos.")


# --- Constantes ---
# Nombres de columnas para el archivo auxiliar SIESA
AUXILIAR_FECHA = 'Fecha'
AUXILIAR_DOCUMENTO = 'Documento'
AUXILIAR_CO = 'C.O.'
AUXILIAR_UN = 'U.N.'
AUXILIAR_DESC_TRANSACCION = 'descripcion_transaccion' # Nombre estándar que queremos al final
AUXILIAR_TEXT1 = 'text1'
AUXILIAR_TEXT2 = 'text2'
AUXILIAR_TEXT3 = 'text3'
AUXILIAR_SALDO_INICIAL = 'saldo_inicial'
AUXILIAR_DEBITO = 'debito' # Nombre estándar singular sin tilde
AUXILIAR_CREDITO = 'credito' # Nombre estándar singular sin tilde
AUXILIAR_SALDO_FINAL = 'saldo_final'

# Índice esperado para la columna de descripción si el nombre no coincide
AUXILIAR_DESC_INDEX = 4 # Quinta columna (índice basado en 0)

# Columnas clave para identificar la cabecera en SIESA (se limpiarán antes de comparar)
AUXILIAR_COLUMNAS_CLAVE_CABECERA = [AUXILIAR_FECHA, AUXILIAR_DOCUMENTO, AUXILIAR_DEBITO, AUXILIAR_CREDITO]
# Columnas finales después de transformar SIESA (estos son los nombres estándar)
AUXILIAR_COLUMNAS_FINALES = [
    'fecha_norm', 'documento_auxiliar', 'descripcion_auxiliar',
    AUXILIAR_DEBITO, AUXILIAR_CREDITO
]


# Nombres de columnas para el extracto Bancolombia (CSV - 9 Columnas)
EXTRACTO_COLUMNAS_CSV_9COLS_CORRECTO = [
    'cuenta_raw', 'codigo_trans_raw', 'col_3_ignorar', 'fecha_raw',
    'col_5_ignorar', 'movimiento_raw', 'codigo_desc_raw', 'descripcion_raw', 'col_9_ignorar'
]
EXTRACTO_COLUMNAS_A_ELIMINAR_9COLS_CORRECTO = [
    'cuenta_raw', 'codigo_trans_raw', 'col_3_ignorar', 'col_5_ignorar',
    'codigo_desc_raw', 'col_9_ignorar'
]
EXTRACTO_COLUMNAS_REQUERIDAS_FUENTE = ['fecha_raw', 'descripcion_raw', 'movimiento_raw']
EXTRACTO_COLUMNAS_FINALES = ['fecha_norm', 'movimiento', 'descripcion_extracto']
EXTRACTO_VALORES_A_EXCLUIR_DESC = ['SALDO DIA', 'SALDO FINAL', 'SALDO INICIAL']

# Nombres de columnas para movimientos Bancolombia (CSV)
MOVIMIENTO_CUENTA = 'cuenta_bancaria'
MOVIMIENTO_FECHA = 'fecha'
MOVIMIENTO_VALOR = 'movimiento'
MOVIMIENTO_DESC = 'descripcion_movimiento'
MOVIMIENTO_COLUMNAS_FIJAS_INDICES = [0, 3, 5, 7]
MOVIMIENTO_COLUMNAS_NOMBRES = [
    MOVIMIENTO_CUENTA, MOVIMIENTO_FECHA, MOVIMIENTO_VALOR, MOVIMIENTO_DESC
]

# Columnas comunes para conciliación
FECHA_CONCILIACION = 'fecha_norm' # Asegúrate que esta definición esté aquí y sea global
MOVIMIENTO_CONCILIACION = 'movimiento' # Asegúrate que esta definición esté aquí y sea global
CONTADOR_CONCILIACION = 'contador'

# --- Funciones de Formateo ---

def clean_text(text: str) -> str:
    """Limpia texto: convierte a minúsculas, quita acentos y espacios."""
    if not isinstance(text, str): text = str(text)
    cleaned = unidecode(text).lower().strip()
    return cleaned

def format_currency(value: any) -> float:
    """Convierte un valor a float, manejando formato monetario (espera '.' decimal)."""
    if pd.isna(value): return 0.0
    try:
        if isinstance(value, str):
            cleaned_value = value.replace('$', '').strip().replace(',', '') # Quita $ y comas (miles)
            return float(cleaned_value) # Asume '.' es decimal
        else: return float(value)
    except (ValueError, TypeError) as e: print(f"WARN format_currency: Valor '{value}' no formateado: {e}"); return 0.0

def format_date_robust(date_value: any) -> Optional[datetime.date]:
    """Intenta convertir un valor a fecha (objeto date)."""
    if pd.isna(date_value) or not date_value: return None
    if isinstance(date_value, datetime): return date_value.date()
    if isinstance(date_value, np.datetime64):
        try:
            ts = pd.Timestamp(date_value)
            return None if pd.isna(ts) else ts.to_pydatetime().date()
        except Exception as e: print(f"WARN format_date np.datetime64: '{date_value}' error: {e}"); return None
    try:
        dt = pd.to_datetime(date_value, errors='coerce', dayfirst=True)
        if pd.isna(dt):
            date_str = str(date_value).strip()
            if len(date_str) == 8 and date_str.isdigit():
                try: dt = datetime.strptime(date_str, '%d%m%Y') # DDMMYYYY
                except ValueError:
                    try: dt = datetime.strptime(date_str, '%Y%m%d') # YYYYMMDD
                    except ValueError: dt = None
            # Añadir otros formatos si es necesario: elif ...
        if pd.isna(dt): return None
        # Asegurar que devuelve datetime.date
        return dt.date() if isinstance(dt, (pd.Timestamp, datetime)) else None
    except Exception as e: print(f"ERROR format_date: '{date_value}' error: {e}"); return None

# --- Funciones de Procesamiento de Archivos ---

def transform_siesa_auxiliary(file_path: str) -> Optional[pd.DataFrame]:
    """Lee y transforma un archivo auxiliar de SIESA (Excel)."""
    try:
        df_excel = pd.read_excel(file_path, header=None, sheet_name=None, dtype=str)
        if not isinstance(df_excel, dict):
             if isinstance(df_excel, pd.DataFrame): df_auxiliar = df_excel
             else: raise ValueError("Formato Excel inesperado.")
        elif not df_excel: raise ValueError("Archivo Excel vacío.")
        else: first_sheet_name = list(df_excel.keys())[0]; print(f"Info: Usando hoja Excel: '{first_sheet_name}'"); df_auxiliar = df_excel[first_sheet_name]
        df_auxiliar.replace(r'^\s*$', pd.NA, regex=True, inplace=True)
        df_auxiliar = df_auxiliar.dropna(how='all').reset_index(drop=True)
        # Detección de cabecera...
        header_row_index = -1; detected_columns = []; max_rows_to_scan = 50
        fecha_clean=clean_text(AUXILIAR_FECHA); doc_clean=clean_text(AUXILIAR_DOCUMENTO); debito_clean=clean_text(AUXILIAR_DEBITO); credito_clean=clean_text(AUXILIAR_CREDITO); debitos_clean='debitos'; creditos_clean='creditos'
        print(f"Info: Buscando cabecera SIESA (primeras {max_rows_to_scan} filas)...")
        for i, row in df_auxiliar.head(max_rows_to_scan).iterrows():
            row_values_clean = {clean_text(v) for v in row.values if pd.notna(v)}
            has_fecha = fecha_clean in row_values_clean; has_doc = doc_clean in row_values_clean
            has_debito = debito_clean in row_values_clean or debitos_clean in row_values_clean
            has_credito = credito_clean in row_values_clean or creditos_clean in row_values_clean
            if has_fecha and has_doc and has_debito and has_credito:
                header_row_index = i
                detected_columns = [str(v).strip() if pd.notna(v) else f'unnamed_{j}' for j, v in enumerate(df_auxiliar.iloc[i])]
                print(f"Info: Cabecera encontrada en fila {i}. Columnas: {detected_columns}")
                break
        if header_row_index == -1: raise ValueError(f"No se encontró cabecera SIESA válida en {file_path}.")
        df_auxiliar.columns = detected_columns; df_data = df_auxiliar.iloc[header_row_index + 1:].reset_index(drop=True)
        # Filtrar filas vacías...
        essential_col_names_orig = [col for col in detected_columns if clean_text(col) in [fecha_clean, doc_clean, debito_clean, debitos_clean, credito_clean, creditos_clean]]
        if essential_col_names_orig:
            cols_to_check_for_na = [col for col in essential_col_names_orig if col in df_data.columns]
            if cols_to_check_for_na:
                original_rows_before_na_drop = len(df_data); df_data = df_data.dropna(subset=cols_to_check_for_na, how='all'); rows_dropped = original_rows_before_na_drop - len(df_data)
                if rows_dropped > 0: print(f"Info: Eliminadas {rows_dropped} filas NaN en SIESA.")
        if df_data.empty: print(f"WARN: No hay datos válidos en SIESA después de filtros."); return None
        # Mapeo de columnas...
        col_map_clean_to_original = {clean_text(col): col for col in detected_columns if isinstance(col, str)}
        fecha_col_orig = col_map_clean_to_original.get(fecha_clean)
        doc_col_orig = col_map_clean_to_original.get(doc_clean)
        debito_col_orig = col_map_clean_to_original.get(debito_clean, col_map_clean_to_original.get(debitos_clean))
        credito_col_orig = col_map_clean_to_original.get(credito_clean, col_map_clean_to_original.get(creditos_clean))
        desc_clean = clean_text(AUXILIAR_DESC_TRANSACCION); desc_col_orig_from_name = col_map_clean_to_original.get(desc_clean)
        desc_col_final_source = None
        if desc_col_orig_from_name and desc_col_orig_from_name in df_data.columns: desc_col_final_source = desc_col_orig_from_name; print(f"Info: Usando descripción SIESA: '{desc_col_final_source}' (por nombre).")
        elif len(detected_columns) > AUXILIAR_DESC_INDEX and detected_columns[AUXILIAR_DESC_INDEX] in df_data.columns: desc_col_final_source = detected_columns[AUXILIAR_DESC_INDEX]; print(f"Info: Usando descripción SIESA: '{desc_col_final_source}' (por índice {AUXILIAR_DESC_INDEX}).")
        else: print(f"WARN: No se encontró columna descripción SIESA ('{desc_clean}' o índice {AUXILIAR_DESC_INDEX}).")
        # Validar columnas esenciales...
        missing_details = []
        if not fecha_col_orig or fecha_col_orig not in df_data.columns: missing_details.append(f"'{AUXILIAR_FECHA}'")
        if not doc_col_orig or doc_col_orig not in df_data.columns: missing_details.append(f"'{AUXILIAR_DOCUMENTO}'")
        if not debito_col_orig or debito_col_orig not in df_data.columns: missing_details.append(f"'{AUXILIAR_DEBITO}(s)'")
        if not credito_col_orig or credito_col_orig not in df_data.columns: missing_details.append(f"'{AUXILIAR_CREDITO}(s)'")
        if missing_details: raise KeyError(f"Faltan columnas SIESA esenciales: {', '.join(missing_details)}. Columnas presentes: {list(df_data.columns)}")
        # Procesar datos seleccionados...
        cols_to_process = [fecha_col_orig, doc_col_orig, debito_col_orig, credito_col_orig];
        if desc_col_final_source: cols_to_process.append(desc_col_final_source)
        df_process = df_data[[col for col in cols_to_process if col in df_data.columns]].copy()
        # Formatear fecha, débito, crédito...
        df_process[FECHA_CONCILIACION] = df_process[fecha_col_orig].apply(format_date_robust)
        print(f"Info SIESA: {df_process[FECHA_CONCILIACION].notna().sum()} de {len(df_process)} fechas parseadas.")
        rows_before_date_drop = len(df_process); df_process = df_process.dropna(subset=[FECHA_CONCILIACION]); rows_after_date_drop = len(df_process)
        if rows_before_date_drop > rows_after_date_drop: print(f"Info: Eliminadas {rows_before_date_drop - rows_after_date_drop} filas SIESA sin fecha válida.")
        if df_process.empty: print(f"WARN: No quedaron filas SIESA válidas."); return None
        df_process[debito_col_orig] = df_process[debito_col_orig].apply(format_currency)
        df_process[credito_col_orig] = df_process[credito_col_orig].apply(format_currency)
        # Construir DataFrame final...
        df_final = pd.DataFrame()
        df_final[FECHA_CONCILIACION] = df_process[FECHA_CONCILIACION]
        df_final['documento_auxiliar'] = df_process[doc_col_orig].astype(str)
        df_final['descripcion_auxiliar'] = df_process[desc_col_final_source].astype(str).fillna('') if desc_col_final_source else ''
        df_final[AUXILIAR_DEBITO] = df_process[debito_col_orig]
        df_final[AUXILIAR_CREDITO] = df_process[credito_col_orig]
        # Validar columnas finales...
        if not all(col in df_final.columns for col in AUXILIAR_COLUMNAS_FINALES): raise KeyError(f"Error interno SIESA: Faltan columnas finales: {[col for col in AUXILIAR_COLUMNAS_FINALES if col not in df_final.columns]}")
        print(f"Info: SIESA procesado. {len(df_final)} filas. Columnas: {list(df_final.columns)}")
        return df_final[AUXILIAR_COLUMNAS_FINALES] # Asegurar orden
    except FileNotFoundError: print(f"ERROR: Archivo SIESA no encontrado: {file_path}"); return None
    except ValueError as ve: print(f"ERROR (ValueError) SIESA: {ve}"); return None
    except KeyError as ke: print(f"ERROR (KeyError) SIESA: Columna {ke}. Verifique estructura."); return None
    except Exception as e: print(f"ERROR inesperado SIESA:"); traceback.print_exc(); return None

def transform_bancolombia_statement(file_path: str) -> Optional[pd.DataFrame]:
    """Lee y transforma un archivo de extracto Bancolombia CSV (9 columnas)."""
    try:
        try: df = pd.read_csv(file_path, sep=None, engine='python', header=None, dtype=str, encoding='utf-8')
        except Exception as read_err: raise ValueError(f"Error leyendo CSV {file_path}: {read_err}") from read_err
        num_cols_actual = df.shape[1]; print(f"Info: Extracto leído con {num_cols_actual} columnas.")
        if num_cols_actual != 9: raise ValueError(f"Extracto debe tener 9 columnas, tiene {num_cols_actual}.")
        df.columns = EXTRACTO_COLUMNAS_CSV_9COLS_CORRECTO; print(f"Info: Columnas Extracto: {list(df.columns)}")
        missing_required = [col for col in EXTRACTO_COLUMNAS_REQUERIDAS_FUENTE if col not in df.columns]
        if missing_required: raise ValueError(f"Faltan columnas fuente requeridas en extracto: {missing_required}.")
        # Procesar datos...
        df[FECHA_CONCILIACION] = df['fecha_raw'].apply(format_date_robust)
        print(f"Info Extracto: {df[FECHA_CONCILIACION].notna().sum()} de {len(df)} fechas parseadas.")
        rows_before = len(df); df = df.dropna(subset=[FECHA_CONCILIACION]); rows_after = len(df)
        if rows_before > rows_after: print(f"Info: Eliminadas {rows_before - rows_after} filas Extracto sin fecha válida.")
        if df.empty: print("WARN: No quedaron filas Extracto válidas post-fecha."); return None
        df[MOVIMIENTO_CONCILIACION] = df['movimiento_raw'].apply(format_currency)
        # Filtrar por descripción...
        if 'descripcion_raw' in df.columns:
            df['desc_upper_temp'] = df['descripcion_raw'].astype(str).str.strip().str.upper()
            rows_before = len(df); df = df[~df['desc_upper_temp'].isin(EXTRACTO_VALORES_A_EXCLUIR_DESC)]; rows_after = len(df)
            if rows_before > rows_after: print(f"Info: Eliminadas {rows_before - rows_after} filas Extracto por descripción excluida.")
            df = df.drop(columns=['desc_upper_temp'])
        if df.empty: print("WARN: No quedaron filas Extracto válidas post-descripción."); return None
        # Crear DataFrame final...
        df_final = pd.DataFrame({
            FECHA_CONCILIACION: df[FECHA_CONCILIACION],
            MOVIMIENTO_CONCILIACION: df[MOVIMIENTO_CONCILIACION],
            'descripcion_extracto': df['descripcion_raw'].astype(str).fillna('') if 'descripcion_raw' in df.columns else ''
        })
        missing_final = [col for col in EXTRACTO_COLUMNAS_FINALES if col not in df_final.columns]
        if missing_final: raise ValueError(f"Error interno Extracto: Faltan columnas finales: {missing_final}")
        print(f"Info: Extracto procesado. {len(df_final)} filas. Columnas: {list(df_final.columns)}")
        return df_final[EXTRACTO_COLUMNAS_FINALES] # Asegurar orden
    except FileNotFoundError: print(f"ERROR: Archivo Extracto no encontrado: {file_path}"); return None
    except ValueError as ve: print(f"ERROR (ValueError) Extracto: {ve}"); return None
    except KeyError as ke: print(f"ERROR (KeyError) Extracto: Columna {ke}. Verifique estructura."); return None
    except Exception as e: print(f"ERROR inesperado Extracto:"); traceback.print_exc(); return None

# --- Función de Conciliación Automática ---
def reconcile_data(df_ledger: pd.DataFrame, df_statement: pd.DataFrame, include_ids: bool = True) -> Optional[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """Realiza conciliación automática por monto y contador."""
    try:
        print("\n--- Iniciando reconcile_data (Automática) ---")
        # Validaciones de entrada...
        if df_ledger is None or df_ledger.empty or df_statement is None or df_statement.empty:
            print("WARN reconcile_data: Uno o ambos DataFrames de entrada están vacíos.")
            # Devolver tupla de DataFrames vacíos para consistencia
            empty_df = pd.DataFrame()
            return empty_df, empty_df, empty_df

        # Validar columnas Ledger
        req_ledger = [FECHA_CONCILIACION, AUXILIAR_DEBITO, AUXILIAR_CREDITO, 'descripcion_auxiliar', 'documento_auxiliar']
        if include_ids: req_ledger.append('tx_id_ref')
        if not all(col in df_ledger.columns for col in req_ledger): raise ValueError(f"Faltan columnas requeridas en Ledger: {[c for c in req_ledger if c not in df_ledger.columns]}")
        # Validar columnas Statement
        req_stmt = [FECHA_CONCILIACION, MOVIMIENTO_CONCILIACION, 'descripcion_extracto']
        if include_ids: req_stmt.append('tx_id_ref')
        if not all(col in df_statement.columns for col in req_stmt): raise ValueError(f"Faltan columnas requeridas en Statement: {[c for c in req_stmt if c not in df_statement.columns]}")

        # Preparar Ledger
        df_ledger_copy = df_ledger.copy()
        df_ledger_copy[MOVIMIENTO_CONCILIACION] = (pd.to_numeric(df_ledger_copy[AUXILIAR_DEBITO], errors='coerce').fillna(0.0) -
                                                pd.to_numeric(df_ledger_copy[AUXILIAR_CREDITO], errors='coerce').fillna(0.0)).round(2) # Redondear a 2 decimales
        df_ledger_copy = df_ledger_copy.sort_values(by=[MOVIMIENTO_CONCILIACION, FECHA_CONCILIACION]).reset_index(drop=True)
        df_ledger_copy[CONTADOR_CONCILIACION] = df_ledger_copy.groupby(MOVIMIENTO_CONCILIACION).cumcount()
        ledger_cols = [MOVIMIENTO_CONCILIACION, CONTADOR_CONCILIACION, FECHA_CONCILIACION, 'documento_auxiliar', 'descripcion_auxiliar', AUXILIAR_DEBITO, AUXILIAR_CREDITO]
        if include_ids: ledger_cols.append('tx_id_ref')
        df_ledger_merge = df_ledger_copy[ledger_cols].rename(columns={FECHA_CONCILIACION: 'fecha_libro'})
        print(f"Ledger listo para merge ({len(df_ledger_merge)} filas).")

        # Preparar Statement
        df_statement_copy = df_statement.copy()
        df_statement_copy[MOVIMIENTO_CONCILIACION] = pd.to_numeric(df_statement_copy[MOVIMIENTO_CONCILIACION], errors='coerce').fillna(0.0).round(2) # Redondear
        df_statement_copy = df_statement_copy.sort_values(by=[MOVIMIENTO_CONCILIACION, FECHA_CONCILIACION]).reset_index(drop=True)
        df_statement_copy[CONTADOR_CONCILIACION] = df_statement_copy.groupby(MOVIMIENTO_CONCILIACION).cumcount()
        statement_cols = [MOVIMIENTO_CONCILIACION, CONTADOR_CONCILIACION, FECHA_CONCILIACION, 'descripcion_extracto']
        if include_ids: statement_cols.append('tx_id_ref')
        df_statement_merge = df_statement_copy[statement_cols].rename(columns={FECHA_CONCILIACION: 'fecha_extracto'})
        print(f"Statement listo para merge ({len(df_statement_merge)} filas).")

        # Realizar Merge
        print(f"Realizando merge 'outer' en [{MOVIMIENTO_CONCILIACION}, {CONTADOR_CONCILIACION}]...")
        reconciled_data = pd.merge(df_ledger_merge, df_statement_merge, on=[MOVIMIENTO_CONCILIACION, CONTADOR_CONCILIACION], how='outer', indicator=True, suffixes=('_libro', '_extracto'))
        print(f"Merge completado. Dimensiones: {reconciled_data.shape}. Distribución:\n{reconciled_data['_merge'].value_counts()}")

        # Separar resultados
        successful = reconciled_data[reconciled_data['_merge'] == 'both'].copy()
        pending = reconciled_data[reconciled_data['_merge'] != 'both'].copy()
        # Limpiar columnas
        successful.drop(columns=[CONTADOR_CONCILIACION, '_merge'], errors='ignore', inplace=True)
        pending.drop(columns=[CONTADOR_CONCILIACION], errors='ignore', inplace=True) # Mantener _merge
        # Renombrar IDs si existen (sufijos _libro/_extracto)
        if include_ids:
            rename_map = {'tx_id_ref_libro': 'tx_id_ref_x', 'tx_id_ref_extracto': 'tx_id_ref_y'}
            successful.rename(columns=rename_map, inplace=True, errors='ignore')
            pending.rename(columns=rename_map, inplace=True, errors='ignore')

        print(f"--- Conciliación (Automática) finalizada ---\nConciliados: {len(successful)}, Pendientes Libro: {len(pending[pending['_merge'] == 'left_only'])}, Pendientes Extracto: {len(pending[pending['_merge'] == 'right_only'])}")
        return reconciled_data, successful, pending
    except Exception as e:
        print(f"ERROR inesperado en reconcile_data:"); traceback.print_exc(); return None

# --- Bloque para ejecución directa (Testing) ---
# (No se ejecuta cuando se importa desde main.py)
if __name__ == "__main__":
    print("--- Ejecutando processing.py directamente para prueba ---")
    # Define rutas a tus archivos locales de prueba
    ruta_auxiliar_siesa = r"G:\Mi unidad\automatizaciones\12_conciliacion_bancaria\siesa_bancolombia_abril_2025.xlsx"
    ruta_extracto_bancolombia = r"G:\Mi unidad\automatizaciones\12_conciliacion_bancaria\CSV_27799726048_000000901195703_20250502_08133217.csv"

    print("\nProcesando archivo auxiliar SIESA...")
    df_libro_test = transform_siesa_auxiliary(ruta_auxiliar_siesa)
    if df_libro_test is not None: print(f"\nLibro SIESA procesado: {len(df_libro_test)} filas.")
    else: print("\nFallo procesando Libro SIESA.")

    print("\nProcesando extracto Bancolombia...")
    df_extracto_test = transform_bancolombia_statement(ruta_extracto_bancolombia)
    if df_extracto_test is not None: print(f"\nExtracto Bancolombia procesado: {len(df_extracto_test)} filas.")
    else: print("\nFallo procesando Extracto Bancolombia.")

    # Intentar conciliación si ambos se procesaron
    if df_libro_test is not None and not df_libro_test.empty and df_extracto_test is not None and not df_extracto_test.empty:
        print("\nRealizando conciliación (prueba)...")
        resultado = reconcile_data(df_libro_test, df_extracto_test, include_ids=False) # Test sin IDs de FastAPI
        if resultado:
            todos_test, conciliados_test, pendientes_test = resultado
            try:
                output_filename_test = 'resultado_conciliacion_prueba.xlsx'
                with pd.ExcelWriter(output_filename_test) as writer:
                    # Usar solo columnas existentes
                    conc_cols = [c for c in ['movimiento', 'fecha_libro', 'documento_auxiliar', 'descripcion_auxiliar', 'debito', 'credito', 'fecha_extracto', 'descripcion_extracto'] if c in conciliados_test.columns]
                    pend_cols = [c for c in ['movimiento', 'fecha_libro', 'documento_auxiliar', 'descripcion_auxiliar', 'debito', 'credito', 'fecha_extracto', 'descripcion_extracto', '_merge'] if c in pendientes_test.columns]
                    conciliados_test[conc_cols].to_excel(writer, sheet_name='Conciliados', index=False)
                    pendientes_test[pend_cols].to_excel(writer, sheet_name='Pendientes', index=False)
                print(f"\nResultados prueba guardados en '{output_filename_test}'")
            except Exception as e: print(f"\nError guardando Excel de prueba: {e}")
        else: print("\nFallo la conciliación (prueba).")
    else: print("\nNo se pueden conciliar datos (prueba) - uno o ambos archivos fallaron o están vacíos.")
    print("\n--- Fin de la ejecución directa de processing.py ---")