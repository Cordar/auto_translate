#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Editor GUI para archivos .po
Permite editar traducciones, pretraducir con DeepL/Google, y copiar traducciones existentes.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import polib

# Un .exe sin consola deja stdout/stderr a None y print() rompe el programa.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
from pathlib import Path
from deep_translator import DeeplTranslator, GoogleTranslator, MyMemoryTranslator
import threading
from typing import Dict, List, Optional, Tuple
import json
import re
from difflib import SequenceMatcher

try:
    import language_tool_python
    LANGUAGE_TOOL_AVAILABLE = True
except ImportError:
    LANGUAGE_TOOL_AVAILABLE = False

class POEditorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Editor de Archivos .po")
        self.root.geometry("1200x800")
        
        self.po_file: Optional[polib.POFile] = None
        self.current_file_path: Optional[Path] = None
        self.entries = []
        self.current_entry_index: Optional[int] = None
        self.is_processing = False
        self.has_unsaved_changes = False
        
        # Metadata personalizada: {index: {'needs_review': bool, 'copied_from': dict}}
        self.entry_metadata: Dict[int, Dict] = {}
        
        # Idiomas disponibles
        self.languages = {
            "Español": "es",
            "Inglés": "en",
            "Catalán": "ca",
            "Francés": "fr",
            "Alemán": "de",
            "Italiano": "it",
            "Portugués": "pt"
        }
        # Cada motor acepta códigos distintos. deep-translator 1.11.4 no incluye catalán en DeepL.
        self.engine_lang_codes = {
            "deepl": {
                "es": "es", "en": "en", "fr": "fr", "de": "de", "it": "it", "pt": "pt"
            },
            "google": {
                "es": "es", "en": "en", "ca": "ca", "fr": "fr", "de": "de", "it": "it", "pt": "pt"
            },
            "mymemory": {
                "es": "es-ES", "en": "en-GB", "ca": "ca-ES", "fr": "fr-FR",
                "de": "de-DE", "it": "it-IT", "pt": "pt-PT"
            },
        }
        
        # Mapeo inverso: código de idioma -> nombre
        self.lang_code_to_name = {v: k for k, v in self.languages.items()}
        # Agregar variantes comunes
        self.lang_code_to_name.update({
            "en": "Inglés",
            "en-GB": "Inglés",
            "en-US": "Inglés",
            "es-ES": "Español",
            "es-MX": "Español",
            "pt-BR": "Portugués",
            "pt-PT": "Portugués",
            "de-DE": "Alemán",
            "de-AT": "Alemán",
            "fr-FR": "Francés",
            "fr-CA": "Francés",
            "it-IT": "Italiano",
            "ca-ES": "Catalán",
            "ca-AD": "Catalán"
        })
        
        self.source_lang = "es"
        self.target_lang = "en"
        
        # Mapeo de idiomas a códigos de LanguageTool
        self.language_tool_codes = {
            "es": "es",
            "en": "en-GB",
            "ca": "ca",
            "fr": "fr",
            "de": "de-DE",
            "it": "it",
            "pt": "pt-PT"
        }
        
        # Configurar cierre de ventana
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.create_widgets()
        self.update_window_title()
    
    def create_widgets(self):
        """Crea los widgets de la interfaz"""
        
        # Frame principal con paneles
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Panel izquierdo: Lista de entradas
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        # Panel derecho: Editor de entrada
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        
        # ========== PANEL IZQUIERDO: Lista de entradas ==========
        left_top = ttk.Frame(left_frame)
        left_top.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(left_top, text="Archivo .po:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_top, text="Cargar...", command=self.load_po_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_top, text="Guardar", command=self.save_po_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_top, text="Guardar como...", command=self.save_po_file_as).pack(side=tk.LEFT, padx=5)
        
        # Filtros y búsqueda
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(filter_frame, text="Filtrar:").pack(side=tk.LEFT, padx=5)
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add('write', self.filter_entries)
        ttk.Entry(filter_frame, textvariable=self.filter_var, width=20).pack(side=tk.LEFT, padx=5)
        
        self.show_translated_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="Solo sin traducir", variable=self.show_translated_var,
                       command=self.filter_entries).pack(side=tk.LEFT, padx=5)
        
        self.show_review_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="Solo a revisar", variable=self.show_review_var,
                       command=self.filter_entries).pack(side=tk.LEFT, padx=5)
        
        # Acciones globales (movidas al panel izquierdo)
        actions_frame = ttk.LabelFrame(left_frame, text="Acciones Globales", padding="10")
        actions_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Configuración de idiomas
        lang_frame = ttk.Frame(actions_frame)
        lang_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(lang_frame, text="Idioma origen:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.source_combo = ttk.Combobox(lang_frame, values=list(self.languages.keys()), state="readonly", width=20)
        self.source_combo.set("Español")
        self.source_combo.grid(row=0, column=1, padx=5, pady=5)
        self.source_combo.bind("<<ComboboxSelected>>", lambda e: self.update_source_lang())
        
        ttk.Label(lang_frame, text="Idioma destino:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_combo = ttk.Combobox(lang_frame, values=list(self.languages.keys()), state="readonly", width=20)
        self.target_combo.set("Inglés")
        self.target_combo.grid(row=1, column=1, padx=5, pady=5)
        self.target_combo.bind("<<ComboboxSelected>>", lambda e: self.update_target_lang())
        
        # Configuración de API key de DeepL (movida a acciones globales)
        deepl_frame = ttk.Frame(actions_frame)
        deepl_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(deepl_frame, text="DeepL API Key (opcional):").pack(side=tk.LEFT, padx=5)
        self.deepl_key_var = tk.StringVar()
        ttk.Entry(deepl_frame, textvariable=self.deepl_key_var, width=30, show="*").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Botones de acciones
        ttk.Button(actions_frame, text="Pretraducir vacías", 
                   command=self.pretranslate_all).pack(fill=tk.X, pady=2)
        self.inconsistency_button = ttk.Button(
            actions_frame,
            text="Inconsistencias (0)",
            command=self.show_inconsistencies,
        )
        self.inconsistency_button.pack(fill=tk.X, pady=2)
        
        copy_frame = ttk.Frame(actions_frame)
        copy_frame.pack(fill=tk.X, pady=5)
        
        self.copy_mode_var = tk.StringVar(value="identical")
        ttk.Radiobutton(copy_frame, text="Idénticas", variable=self.copy_mode_var, 
                       value="identical").pack(side=tk.LEFT, padx=5, pady=3)
        ttk.Radiobutton(copy_frame, text="Similares", variable=self.copy_mode_var, 
                       value="similar").pack(side=tk.LEFT, padx=5, pady=3)
        ttk.Radiobutton(copy_frame, text="A revisar", variable=self.copy_mode_var, 
                       value="to_review").pack(side=tk.LEFT, padx=5, pady=3)
        
        copy_actions = ttk.Frame(actions_frame)
        copy_actions.pack(fill=tk.X, pady=2)
        
        self.copy_mark_review_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(copy_actions, text="Marcar como 'a revisar'", 
                       variable=self.copy_mark_review_var).pack(side=tk.LEFT, padx=5, pady=3)
        
        ttk.Button(copy_actions, text="Copiar Traducciones", 
                  command=self.copy_translations).pack(side=tk.LEFT, padx=5, pady=5, ipady=3)
        
        # Lista de entradas
        list_frame = ttk.LabelFrame(left_frame, text="Entradas", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview para la lista
        columns = ("#", "Estado", "MsgID")
        self.entries_tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=20)
        self.entries_tree.heading("#0", text="")
        self.entries_tree.heading("#", text="#")
        self.entries_tree.heading("Estado", text="Estado")
        self.entries_tree.heading("MsgID", text="MsgID (preview)")
        self.entries_tree.column("#0", width=0, stretch=False)
        self.entries_tree.column("#", width=50, stretch=False)
        self.entries_tree.column("Estado", width=120, stretch=False)
        self.entries_tree.column("MsgID", width=300)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.entries_tree.yview)
        self.entries_tree.configure(yscrollcommand=scrollbar.set)
        
        self.entries_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.entries_tree.bind("<<TreeviewSelect>>", self.on_entry_select)
        
        # Contadores de estadísticas (movidas abajo de la lista)
        stats_frame = ttk.LabelFrame(left_frame, text="Estadísticas", padding="10")
        stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Frame para traducciones
        trans_stats = ttk.Frame(stats_frame)
        trans_stats.pack(fill=tk.X, pady=2)
        ttk.Label(trans_stats, text="Traducciones:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        self.translated_count_label = ttk.Label(trans_stats, text="0/0", foreground="green")
        self.translated_count_label.pack(side=tk.LEFT, padx=5)
        ttk.Label(trans_stats, text="traducidas").pack(side=tk.LEFT)
        
        # Frame para revisión
        review_stats = ttk.Frame(stats_frame)
        review_stats.pack(fill=tk.X, pady=2)
        ttk.Label(review_stats, text="Revisión:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        self.review_count_label = ttk.Label(review_stats, text="0/0", foreground="orange")
        self.review_count_label.pack(side=tk.LEFT, padx=5)
        ttk.Label(review_stats, text="a revisar").pack(side=tk.LEFT)
        
        # ========== PANEL DERECHO: Editor de entrada ==========
        right_top = ttk.Frame(right_frame)
        right_top.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(right_top, text="Editor de Entrada", font=("Arial", 12, "bold")).pack()
        
        # MsgID (no editable)
        msgid_frame = ttk.LabelFrame(right_frame, text="MsgID (Original)", padding="10")
        msgid_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        msgid_top = ttk.Frame(msgid_frame)
        msgid_top.pack(fill=tk.X, pady=5)
        
        self.msgid_text = scrolledtext.ScrolledText(msgid_frame, height=5, wrap=tk.WORD, state=tk.DISABLED)
        self.msgid_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        ttk.Button(msgid_top, text="📋 Copiar MsgID", command=self.copy_msgid_to_clipboard).pack(side=tk.LEFT, padx=5)
        
        # MsgStr (editable)
        msgstr_frame = ttk.LabelFrame(right_frame, text="Traducción (MsgStr)", padding="10")
        msgstr_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Label para mostrar "copiada de" y Speaker (arriba del campo de texto)
        self.copied_from_label = ttk.Label(msgstr_frame, text="", foreground="blue", font=("Arial", 9, "italic"))
        self.copied_from_label.pack(fill=tk.X, padx=5, pady=2)
        
        self.msgstr_text = scrolledtext.ScrolledText(msgstr_frame, height=8, wrap=tk.WORD)
        self.msgstr_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.msgstr_text.bind("<KeyRelease>", self.on_translation_changed)
        
        # Frame para información con etiquetas azules (debajo del campo de texto)
        info_frame = ttk.Frame(msgstr_frame)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Labels para información (Speaker, etc.)
        self.speaker_label = ttk.Label(info_frame, text="", foreground="blue", font=("Arial", 9, "bold"))
        self.speaker_label.pack(side=tk.LEFT, padx=5)
        
        self.copied_from_info_label = ttk.Label(info_frame, text="", foreground="blue", font=("Arial", 9))
        self.copied_from_info_label.pack(side=tk.LEFT, padx=5)
        
        # Botones de acción para entrada actual
        entry_actions = ttk.Frame(right_frame)
        entry_actions.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(entry_actions, text="Traducir esta entrada", 
                  command=self.translate_current).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_actions, text="Corregir", 
                  command=self.correct_current).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_actions, text="Limpiar", 
                  command=self.clear_current_translation).pack(side=tk.LEFT, padx=5)
        
        # Botones de navegación (se mostrarán/ocultarán dinámicamente)
        self.next_untranslated_btn = ttk.Button(
            entry_actions, 
            text="Siguiente sin traducir", 
            command=self.next_untranslated
        )
        
        self.next_review_btn = ttk.Button(
            entry_actions, 
            text="Siguiente a revisar", 
            command=self.next_needs_review
        )
        
        self.okay_btn = ttk.Button(
            entry_actions, 
            text="✓ Marcar como Revisado", 
            command=self.mark_as_okay
        )
        
        # Checkbox para marcar "a revisar"
        self.needs_review_var = tk.BooleanVar()
        self.needs_review_check = ttk.Checkbutton(
            entry_actions, 
            text="A revisar", 
            variable=self.needs_review_var,
            command=self.toggle_needs_review
        )
        self.needs_review_check.pack(side=tk.LEFT, padx=5)
        
        # Metadata
        metadata_frame = ttk.LabelFrame(right_frame, text="Metadata", padding="10")
        metadata_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.metadata_text = scrolledtext.ScrolledText(metadata_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.metadata_text.pack(fill=tk.BOTH, expand=True)
        
        # Barra de estado
        self.status_bar = ttk.Label(right_frame, text="Listo", relief=tk.SUNKEN)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
    
    def update_window_title(self):
        """Actualiza el título de la ventana con indicador de cambios sin guardar"""
        title = "Editor de Archivos .po"
        if self.current_file_path:
            title += f" - {self.current_file_path.name}"
        if self.has_unsaved_changes:
            title += " *"
        self.root.title(title)
    
    def update_statistics(self):
        """Actualiza los contadores de estadísticas"""
        if not self.entries:
            self.translated_count_label.config(text="0/0")
            self.review_count_label.config(text="0/0")
            if hasattr(self, "inconsistency_button"):
                self.inconsistency_button.config(text="Inconsistencias (0)")
            return
        
        total = len(self.entries)
        translated = 0
        needs_review = 0
        
        for i, entry in enumerate(self.entries):
            if entry.translated():
                translated += 1
            
            if self.entry_metadata.get(i, {}).get('needs_review', False):
                needs_review += 1
        
        untranslated = total - translated
        reviewed = total - needs_review
        
        # Actualizar etiquetas
        self.translated_count_label.config(text=f"{translated}/{total}")
        self.review_count_label.config(text=f"{needs_review}/{total}")
        
        # Cambiar color según el progreso
        if translated == total:
            self.translated_count_label.config(foreground="green")
        elif translated > 0:
            self.translated_count_label.config(foreground="blue")
        else:
            self.translated_count_label.config(foreground="red")
        
        if hasattr(self, "inconsistency_button"):
            conflict_count = len(self._inconsistent_groups())
            self.inconsistency_button.config(text=f"Inconsistencias ({conflict_count})")
        
        if needs_review == 0:
            self.review_count_label.config(foreground="green")
        elif needs_review < total:
            self.review_count_label.config(foreground="orange")
        else:
            self.review_count_label.config(foreground="red")
    
    def update_source_lang(self):
        """Actualiza el idioma origen"""
        lang_name = self.source_combo.get()
        self.source_lang = self.languages.get(lang_name, "es")
    
    def update_target_lang(self):
        """Actualiza el idioma destino"""
        lang_name = self.target_combo.get()
        self.target_lang = self.languages.get(lang_name, "en")
    
    def copy_msgid_to_clipboard(self):
        """Copia el msgid actual al portapapeles"""
        if self.current_entry_index is None:
            return
        
        entry = self.entries[self.current_entry_index]
        text_to_copy = entry.msgid
        if entry.msgid_plural:
            text_to_copy += f"\n{entry.msgid_plural}"
        
        self.root.clipboard_clear()
        self.root.clipboard_append(text_to_copy)
        self.status_bar.config(text="MsgID copiado al portapapeles")
    
    def extract_speaker_from_metadata(self, entry):
        """Extrae información de Speaker o Context de los comentarios"""
        speaker = None
        
        # Buscar en comment
        if entry.comment:
            # Buscar "Speaker": "NAME"
            match = re.search(r'"Speaker"\s*:\s*"([^"]+)"', entry.comment)
            if match:
                speaker = match.group(1).strip()
            else:
                # Buscar "Context": "SPEAKER ->" o "Context" : "DV_M -> "
                # Captura el texto antes del "->" (puede haber espacios)
                match = re.search(r'"Context"\s*:\s*"([^"]*?)\s*->\s*"', entry.comment)
                if match:
                    speaker = match.group(1).strip()
        
        # Buscar en tcomment si no se encontró
        if not speaker and entry.tcomment:
            match = re.search(r'"Speaker"\s*:\s*"([^"]+)"', entry.tcomment)
            if match:
                speaker = match.group(1).strip()
            else:
                # Buscar "Context": "SPEAKER ->" o "Context" : "DV_M -> "
                match = re.search(r'"Context"\s*:\s*"([^"]*?)\s*->\s*"', entry.tcomment)
                if match:
                    speaker = match.group(1).strip()
        
        return speaker
    
    def load_po_file(self):
        """Carga un archivo .po"""
        if self.has_unsaved_changes:
            response = messagebox.askyesnocancel(
                "Cambios sin guardar",
                "Tienes cambios sin guardar. ¿Deseas guardarlos antes de cargar otro archivo?\n\n"
                "Sí: Guardar y continuar\n"
                "No: Descartar cambios y continuar\n"
                "Cancelar: Volver al editor"
            )
            if response is True:
                if not self.save_po_file():
                    return  # Usuario canceló el guardado
            elif response is None:
                return  # Usuario canceló
        
        filename = filedialog.askopenfilename(
            title="Seleccionar archivo .po",
            filetypes=[("Archivos PO", "*.po"), ("Todos los archivos", "*.*")]
        )
        
        if filename:
            try:
                self.po_file = polib.pofile(filename)
                self.current_file_path = Path(filename)
                self.entries = list(self.po_file)
                
                # Limpiar entradas con msgstr None (convertir a string vacío)
                self.clean_none_msgstr()
                
                # Detectar idiomas automáticamente
                self.detect_languages_from_po()
                
                # Ordenar por nombre de archivo
                self.sort_entries_by_filename()
                
                # Cargar metadata personalizada
                self.load_metadata_from_po()
                
                self.update_entries_list()
                self.update_window_title()
                self.has_unsaved_changes = False
                self.status_bar.config(text=f"Archivo cargado: {Path(filename).name} ({len(self.entries)} entradas)")
            except Exception as e:
                messagebox.showerror("Error", f"Error al cargar el archivo:\n{str(e)}")
    
    def clean_none_msgstr(self):
        """Limpia entradas con msgstr None, convirtiéndolas a string vacío"""
        for entry in self.entries:
            if entry.msgid_plural:
                # Limpiar plurales
                for idx in list(entry.msgstr_plural.keys()):
                    if entry.msgstr_plural[idx] is None:
                        entry.msgstr_plural[idx] = ""
                    else:
                        entry.msgstr_plural[idx] = str(entry.msgstr_plural[idx])
            else:
                # Limpiar msgstr simple
                if entry.msgstr is None:
                    entry.msgstr = ""
                else:
                    entry.msgstr = str(entry.msgstr)
    
    def detect_languages_from_po(self):
        """Detecta automáticamente los idiomas de origen y destino desde el archivo .po"""
        detected_target = None
        detected_source = None
        
        # Intentar detectar desde los metadatos del archivo
        if self.po_file.metadata:
            # Buscar Language en los metadatos
            language = self.po_file.metadata.get('Language', '')
            if language:
                # Normalizar el código de idioma (puede venir como "es_ES", "es-ES", "es", etc.)
                lang_code = language.replace('_', '-').split('-')[0].lower()
                # Intentar encontrar variante completa
                for code, name in self.lang_code_to_name.items():
                    if code.lower().startswith(lang_code) or lang_code in code.lower():
                        detected_target = code
                        break
                # Si no encontramos variante, usar el código base
                if not detected_target:
                    # Mapear códigos comunes
                    lang_map = {
                        'es': 'es', 'en': 'en', 'ca': 'ca', 'fr': 'fr',
                        'de': 'de', 'it': 'it', 'pt': 'pt'
                    }
                    detected_target = lang_map.get(lang_code, None)
        
        # Intentar detectar desde el nombre del archivo
        if not detected_target and self.current_file_path:
            filename = self.current_file_path.stem.lower()
            # Buscar patrones como messages_es.po, es.po, etc.
            for code, name in self.lang_code_to_name.items():
                code_lower = code.lower().replace('-', '_')
                if f'_{code_lower}' in filename or filename.endswith(code_lower):
                    detected_target = code
                    break
        
        # Si detectamos el idioma destino, actualizar
        if detected_target:
            target_name = self.lang_code_to_name.get(detected_target)
            if target_name and target_name in self.languages:
                self.target_lang = detected_target
                self.target_combo.set(target_name)
        
        # Para el idioma origen, asumimos español por defecto (o el que esté configurado)
        # Si la mayoría de msgid están en otro idioma, podríamos detectarlo, pero es complejo
        # Por ahora, mantenemos el valor actual o español por defecto
        
        # Si no se pudo detectar el idioma destino, mostrar diálogo
        if not detected_target:
            self.show_language_selection_dialog()
    
    def show_language_selection_dialog(self):
        """Muestra un diálogo para seleccionar el idioma destino si no se pudo detectar"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Seleccionar Idioma Destino")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrar la ventana
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        ttk.Label(dialog, text="No se pudo detectar el idioma destino automáticamente.\n\nSelecciona el idioma al que quieres traducir:",
                 font=("Arial", 10)).pack(pady=20)
        
        selected_lang = tk.StringVar(value="Inglés")
        lang_combo = ttk.Combobox(dialog, textvariable=selected_lang, 
                                 values=list(self.languages.keys()), 
                                 state="readonly", width=30)
        lang_combo.pack(pady=10)
        
        def on_ok():
            lang_name = selected_lang.get()
            if lang_name in self.languages:
                self.target_lang = self.languages[lang_name]
                self.target_combo.set(lang_name)
            dialog.destroy()
        
        def on_cancel():
            # Mantener el valor por defecto
            dialog.destroy()
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Aceptar", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancelar", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        # Hacer que Enter seleccione
        dialog.bind('<Return>', lambda e: on_ok())
        lang_combo.focus()
    
    def sort_entries_by_filename(self):
        """Ordena las entradas por nombre de archivo (de occurrences)"""
        def get_filename(entry):
            if entry.occurrences:
                # Obtener el primer archivo de occurrences
                return entry.occurrences[0][0]
            return ""
        
        self.entries.sort(key=get_filename)
    
    def load_metadata_from_po(self):
        """Carga metadata personalizada desde los comentarios del archivo .po"""
        print(f"\n[DEBUG load_metadata_from_po] INICIO")
        # Primero, crear un diccionario temporal indexado por msgid
        temp_metadata_by_msgid = {}
        
        for entry in self.entries:
            if entry.tcomment:
                # Buscar líneas con POEDITOR_METADATA:
                lines = entry.tcomment.split('\n')
                metadata_lines = [line for line in lines if line.strip().startswith('POEDITOR_METADATA:')]
                
                for metadata_line in metadata_lines:
                    # Extraer el JSON después de POEDITOR_METADATA:
                    json_str = metadata_line.replace('POEDITOR_METADATA:', '').strip()
                    if json_str:
                        try:
                            metadata = json.loads(json_str)
                            temp_metadata_by_msgid[entry.msgid] = metadata
                            print(f"[DEBUG load_metadata_from_po] Cargada metadata para msgid '{entry.msgid[:50]}...': {metadata}")
                        except json.JSONDecodeError:
                            # Ignorar JSON inválido silenciosamente
                            print(f"[DEBUG load_metadata_from_po] ERROR: JSON inválido para msgid '{entry.msgid[:50]}...'")
                            pass
        
        # Ahora mapear la metadata a los índices actuales después de ordenar
        self.entry_metadata = {}
        for i, entry in enumerate(self.entries):
            if entry.msgid in temp_metadata_by_msgid:
                self.entry_metadata[i] = temp_metadata_by_msgid[entry.msgid]
                print(f"[DEBUG load_metadata_from_po] Mapeada metadata a índice {i}: {self.entry_metadata[i]}")
        
        print(f"[DEBUG load_metadata_from_po] Total entradas con metadata: {len(self.entry_metadata)}")
        print(f"[DEBUG load_metadata_from_po] FIN\n")
    
    def save_metadata_to_po(self):
        """Guarda metadata personalizada en los comentarios del archivo .po"""
        print(f"\n[DEBUG save_metadata_to_po] INICIO")
        print(f"[DEBUG save_metadata_to_po] Total entradas con metadata: {len(self.entry_metadata)}")
        # Primero, limpiar TODAS las líneas POEDITOR_METADATA de TODAS las entradas
        # Esto asegura que cualquier metadata antigua se elimine
        for entry in self.entries:
            if entry.tcomment:
                lines = entry.tcomment.split('\n')
                # Filtrar todas las líneas que empiezan con POEDITOR_METADATA:
                filtered_lines = [line for line in lines if not line.strip().startswith('POEDITOR_METADATA:')]
                # Reconstruir tcomment sin las líneas de metadata
                entry.tcomment = '\n'.join(filtered_lines).strip()
                # Si queda vacío, establecer a None
                if not entry.tcomment:
                    entry.tcomment = None
        
        # Luego, agregar metadata solo para las entradas que realmente la necesitan
        saved_count = 0
        for i, entry in enumerate(self.entries):
            if i in self.entry_metadata:
                metadata = self.entry_metadata[i]
                # Solo guardar si tiene needs_review=True o copied_from
                # Si needs_review es False, no guardar nada (ya se limpió arriba)
                needs_review = metadata.get('needs_review', False)
                copied_from = metadata.get('copied_from')
                
                print(f"[DEBUG save_metadata_to_po] Entrada {i}: needs_review={needs_review}, copied_from={copied_from is not None}")
                
                if needs_review or copied_from:
                    # Crear un diccionario limpio solo con lo que queremos guardar
                    clean_metadata = {}
                    if needs_review:
                        clean_metadata['needs_review'] = True
                    if copied_from:
                        clean_metadata['copied_from'] = copied_from
                    
                    # Serializar metadata a JSON compacto
                    json_str = json.dumps(clean_metadata, ensure_ascii=False, separators=(',', ':'))
                    
                    # Agregar nueva metadata
                    metadata_line = f"POEDITOR_METADATA:{json_str}"
                    if entry.tcomment:
                        entry.tcomment = f"{entry.tcomment}\n{metadata_line}"
                    else:
                        entry.tcomment = metadata_line
                    
                    saved_count += 1
                    print(f"[DEBUG save_metadata_to_po] Guardada metadata para entrada {i}: {clean_metadata}")
        
        print(f"[DEBUG save_metadata_to_po] Total metadata guardada: {saved_count}")
        print(f"[DEBUG save_metadata_to_po] FIN\n")
    
    def save_po_file(self):
        """Guarda el archivo .po actual"""
        if not self.po_file or not self.current_file_path:
            return self.save_po_file_as()
        
        try:
            # Guardar metadata antes de guardar
            self.save_metadata_to_po()
            
            self.po_file.save(str(self.current_file_path))
            self.has_unsaved_changes = False
            self.update_window_title()
            self.status_bar.config(text=f"Archivo guardado: {self.current_file_path.name}")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar el archivo:\n{str(e)}")
            return False
    
    def save_po_file_as(self):
        """Guarda el archivo .po con un nuevo nombre"""
        if not self.po_file:
            messagebox.showwarning("Advertencia", "No hay archivo cargado.")
            return False
        
        filename = filedialog.asksaveasfilename(
            title="Guardar archivo .po como",
            defaultextension=".po",
            filetypes=[("Archivos PO", "*.po"), ("Todos los archivos", "*.*")]
        )
        
        if filename:
            try:
                self.current_file_path = Path(filename)
                # Guardar metadata antes de guardar
                self.save_metadata_to_po()
                
                self.po_file.save(filename)
                self.has_unsaved_changes = False
                self.update_window_title()
                self.status_bar.config(text=f"Archivo guardado: {self.current_file_path.name}")
                return True
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar el archivo:\n{str(e)}")
                return False
        return False
    
    def filter_entries(self, *args):
        """Filtra las entradas según los criterios"""
        self.update_entries_list()
    
    def update_entries_list(self):
        """Actualiza la lista de entradas"""
        print(f"\n[DEBUG update_entries_list] INICIO")
        # Preservar el índice de la entrada seleccionada antes de limpiar
        selected_index = self.current_entry_index
        print(f"[DEBUG update_entries_list] selected_index preservado: {selected_index}")
        
        # Preservar el foco y la posición del cursor del campo de texto
        text_widget_has_focus = self.msgstr_text.focus_get() == self.msgstr_text
        cursor_pos = None
        if text_widget_has_focus:
            try:
                cursor_pos = self.msgstr_text.index(tk.INSERT)
            except:
                pass
        
        print(f"[DEBUG update_entries_list] text_widget_has_focus: {text_widget_has_focus}")
        
        # Limpiar lista
        for item in self.entries_tree.get_children():
            self.entries_tree.delete(item)
        
        # Filtrar entradas
        filter_text = self.filter_var.get().lower()
        show_only_untranslated = self.show_translated_var.get()
        show_only_review = self.show_review_var.get()
        
        print(f"[DEBUG update_entries_list] Filtros - texto: '{filter_text}', solo sin traducir: {show_only_untranslated}, solo a revisar: {show_only_review}")
        
        selected_item_id = None
        
        for i, entry in enumerate(self.entries):
            # Filtrar por texto
            if filter_text and filter_text not in entry.msgid.lower():
                continue
            
            # Filtrar por estado de traducción
            if show_only_untranslated and entry.translated():
                continue
            
            # Filtrar por "a revisar"
            if show_only_review:
                needs_review = self.entry_metadata.get(i, {}).get('needs_review', False)
                if not needs_review:
                    continue
            
            # Determinar estado
            needs_review = self.entry_metadata.get(i, {}).get('needs_review', False)
            
            if entry.translated():
                if needs_review:
                    status = "⚠ A revisar"
                else:
                    status = "✓ Traducida"
            elif entry.msgid_plural:
                if needs_review:
                    status = "⚠ Plural (revisar)"
                else:
                    status = "Plural"
            else:
                if needs_review:
                    status = "⚠ Sin traducir"
                else:
                    status = "Sin traducir"
            
            # Preview del msgid (primeros 50 caracteres)
            msgid_preview = entry.msgid[:50] + "..." if len(entry.msgid) > 50 else entry.msgid
            
            # Insertar en el tree
            item_id = self.entries_tree.insert("", tk.END, values=(i+1, status, msgid_preview))
            
            # Si esta es la entrada que estaba seleccionada, guardar su item_id
            if selected_index is not None and i == selected_index:
                selected_item_id = item_id
                print(f"[DEBUG update_entries_list] Entrada seleccionada encontrada en lista, item_id: {item_id}")
            
            # Marcar visualmente las que necesitan revisión
            if needs_review:
                self.entries_tree.set(item_id, "Estado", status)
        
        # Asegurar que current_entry_index se mantiene siempre
        # (incluso si la entrada no está visible debido a filtros)
        if selected_index is not None:
            self.current_entry_index = selected_index
            print(f"[DEBUG update_entries_list] current_entry_index restaurado a: {self.current_entry_index}")
        else:
            print(f"[DEBUG update_entries_list] WARNING: selected_index era None, current_entry_index: {self.current_entry_index}")
        
        # Restaurar la selección si había una entrada seleccionada y está visible
        # Siempre restaurar la selección para mantener la sincronización, incluso si el campo de texto tiene el foco
        # (el foco se restaurará después)
        if selected_item_id:
            print(f"[DEBUG update_entries_list] Restaurando selección del treeview (item_id: {selected_item_id})")
            # Usar after_idle para evitar conflictos con eventos de foco
            self.root.after_idle(lambda: self.entries_tree.selection_set(selected_item_id))
            self.root.after_idle(lambda: self.entries_tree.see(selected_item_id))
        elif selected_item_id is None and selected_index is not None:
            print(f"[DEBUG update_entries_list] WARNING: Entrada {selected_index} no está visible en la lista filtrada")
            # Aunque no esté visible, mantener el índice para que mark_as_okay pueda funcionar
            print(f"[DEBUG update_entries_list] Manteniendo current_entry_index {selected_index} aunque no esté visible")
        
        # Restaurar el foco y la posición del cursor del campo de texto inmediatamente
        if text_widget_has_focus:
            self.msgstr_text.focus_set()
            if cursor_pos:
                self.msgstr_text.mark_set(tk.INSERT, cursor_pos)
        
        # Actualizar estadísticas
        self.update_statistics()
        print(f"[DEBUG update_entries_list] FIN - current_entry_index final: {self.current_entry_index}\n")
    
    def on_entry_select(self, event):
        """Se ejecuta cuando se selecciona una entrada de la lista"""
        selection = self.entries_tree.selection()
        
        if not selection:
            # Si no hay selección pero tenemos un current_entry_index válido, no lo borremos
            if self.current_entry_index is not None and 0 <= self.current_entry_index < len(self.entries):
                return
            self.current_entry_index = None
            return
        
        item = selection[0]
        values = self.entries_tree.item(item)['values']
        if not values:
            if self.current_entry_index is not None and 0 <= self.current_entry_index < len(self.entries):
                return
            self.current_entry_index = None
            return
        
        index = int(values[0]) - 1
        if 0 <= index < len(self.entries):
            # Establecer el índice ANTES de llamar a display_entry
            self.current_entry_index = index
            self.display_entry(self.entries[index])
    
    def display_entry(self, entry):
        """Muestra una entrada en el editor"""
        # Preservar la posición del cursor antes de actualizar
        try:
            cursor_pos = self.msgstr_text.index(tk.INSERT)
            has_focus = self.msgstr_text.focus_get() == self.msgstr_text
        except:
            cursor_pos = None
            has_focus = False
        
        # MsgID
        self.msgid_text.config(state=tk.NORMAL)
        self.msgid_text.delete(1.0, tk.END)
        msgid_display = entry.msgid
        if entry.msgid_plural:
            msgid_display += f"\n\nPlural:\n{entry.msgid_plural}"
        self.msgid_text.insert(1.0, msgid_display)
        self.msgid_text.config(state=tk.DISABLED)
        
        # MsgStr - solo actualizar si no tiene el foco (para no interrumpir la escritura)
        if not has_focus:
            self.msgstr_text.delete(1.0, tk.END)
            if entry.msgid_plural:
                # Mostrar plurales en formato [0]: texto\n[1]: texto
                plural_lines = []
                for idx in sorted(entry.msgstr_plural.keys()):
                    text = entry.msgstr_plural.get(idx, "")
                    if text is None:
                        text = ""
                    plural_lines.append(f"[{idx}]: {text}")
                text_to_insert = "\n".join(plural_lines) if plural_lines else ""
                if text_to_insert:
                    self.msgstr_text.insert(1.0, text_to_insert)
            else:
                # Asegurar que msgstr sea un string válido (no None)
                text_to_insert = str(entry.msgstr) if entry.msgstr is not None else ""
                if text_to_insert:
                    self.msgstr_text.insert(1.0, text_to_insert)
        
        # Estado de "a revisar"
        needs_review = self.entry_metadata.get(self.current_entry_index, {}).get('needs_review', False)
        self.needs_review_var.set(needs_review)
        
        # Mostrar información de "copiada de" y Speaker
        entry_meta = self.entry_metadata.get(self.current_entry_index, {})
        copied_from = entry_meta.get('copied_from')
        speaker = self.extract_speaker_from_metadata(entry)
        
        # Actualizar label superior (solo "copiada de", sin speaker)
        copied_from_text = ""
        if copied_from:
            source_index = copied_from.get('index', '')
            copied_from_text = f"📋 Copiada de entrada #{source_index + 1}"
        
        self.copied_from_label.config(text=copied_from_text)
        
        # Actualizar etiquetas azules debajo del campo de texto
        # Speaker
        if speaker:
            self.speaker_label.config(text=f"🎭 Speaker: {speaker}")
            self.speaker_label.pack(side=tk.LEFT, padx=5)
        else:
            self.speaker_label.config(text="")
            self.speaker_label.pack_forget()
        
        # Información de "copiada de"
        if copied_from:
            source_index = copied_from.get('index', '')
            source_speaker = copied_from.get('speaker', '')
            if source_speaker:
                self.copied_from_info_label.config(text=f"📋 Copiada de entrada #{source_index + 1} (Speaker: {source_speaker})")
            else:
                self.copied_from_info_label.config(text=f"📋 Copiada de entrada #{source_index + 1}")
            self.copied_from_info_label.pack(side=tk.LEFT, padx=5)
        else:
            self.copied_from_info_label.config(text="")
            self.copied_from_info_label.pack_forget()
        
        # Mostrar/ocultar botones de navegación según el estado
        is_translated = entry.translated()
        
        # Ocultar todos primero
        self.next_untranslated_btn.pack_forget()
        self.next_review_btn.pack_forget()
        self.okay_btn.pack_forget()
        
        # Solo mostrar botones si hay una entrada seleccionada
        if self.current_entry_index is not None:
            if needs_review:
                # Si está marcada como "a revisar", mostrar botón "Siguiente a revisar" y "Okay"
                self.next_review_btn.pack(side=tk.LEFT, padx=5)
                self.okay_btn.pack(side=tk.LEFT, padx=5)
            elif not is_translated:
                # Si no está traducida, mostrar "Siguiente sin traducir"
                self.next_untranslated_btn.pack(side=tk.LEFT, padx=5)
            # Si está traducida y no necesita revisión, no mostrar ningún botón de navegación
        
        # Metadata
        self.metadata_text.config(state=tk.NORMAL)
        self.metadata_text.delete(1.0, tk.END)
        
        metadata_info = []
        if entry.comment:
            metadata_info.append(f"Comentario: {entry.comment}")
        if entry.tcomment:
            # Filtrar líneas de POEDITOR_METADATA para mostrar
            tcomment_lines = entry.tcomment.split('\n')
            filtered_tcomment = [line for line in tcomment_lines if not line.strip().startswith('POEDITOR_METADATA:')]
            if filtered_tcomment:
                metadata_info.append(f"Comentario del traductor: {''.join(filtered_tcomment)}")
        if entry.occurrences:
            metadata_info.append(f"Ocurrencias: {', '.join([f'{f}:{l}' for f, l in entry.occurrences])}")
        if entry.flags:
            metadata_info.append(f"Flags: {', '.join(entry.flags)}")
        if entry.previous_msgid:
            metadata_info.append(f"MsgID anterior: {entry.previous_msgid}")
        if entry.previous_msgctxt:
            metadata_info.append(f"Contexto anterior: {entry.previous_msgctxt}")
        
        # Mostrar información de copia si existe
        if self.current_entry_index is not None:
            entry_meta = self.entry_metadata.get(self.current_entry_index, {})
            copied_from = entry_meta.get('copied_from')
            if copied_from:
                metadata_info.append("")
                metadata_info.append("=" * 50)
                metadata_info.append("INFORMACIÓN DE COPIA:")
                source_index = copied_from.get('index', 'N/A')
                source_speaker = copied_from.get('speaker', 'N/A')
                metadata_info.append(f"  Copiada de entrada #{source_index + 1}")
                metadata_info.append(f"  Speaker original: {source_speaker}")
        
        self.metadata_text.insert(1.0, "\n".join(metadata_info))
        self.metadata_text.config(state=tk.DISABLED)
    
    def on_translation_changed(self, event=None):
        """Se ejecuta cuando se modifica la traducción - SOLO actualiza el texto en memoria, sin refrescar UI"""
        if self.current_entry_index is None:
            return
        
        entry = self.entries[self.current_entry_index]
        new_translation = self.msgstr_text.get(1.0, tk.END).strip()
        
        # Actualizar el texto en la entrada
        if entry.msgid_plural:
            # Manejar plurales (formato: [0]: texto\n[1]: texto)
            lines = new_translation.split('\n')
            entry.msgstr_plural.clear()
            for line in lines:
                if ':' in line:
                    idx_str, text = line.split(':', 1)
                    try:
                        idx = int(idx_str.strip().strip('[]'))
                        text_value = text.strip() if text else ""
                        entry.msgstr_plural[idx] = str(text_value) if text_value is not None else ""
                    except ValueError:
                        pass
        else:
            # Asegurar que msgstr siempre sea un string válido
            entry.msgstr = str(new_translation) if new_translation is not None else ""
        
        # Sincronizar el estado de "a revisar" con metadata si el checkbox está marcado
        if self.needs_review_var.get():
            if self.current_entry_index not in self.entry_metadata:
                self.entry_metadata[self.current_entry_index] = {}
            self.entry_metadata[self.current_entry_index]['needs_review'] = True
        
        # Marcar como cambios sin guardar (sin refrescar la lista ni la UI)
        self.has_unsaved_changes = True
        self.update_window_title()
    
    def _has_translation_text(self, entry) -> bool:
        """True si la entrada ya tiene texto traducido, aunque esté marcada fuzzy."""
        if entry.msgid_plural:
            return any(str(value or "").strip() for value in entry.msgstr_plural.values())
        return bool(str(entry.msgstr or "").strip())

    def _translation_snapshot(self, entry):
        """Texto traducido, para saber si una copia ha cambiado la entrada."""
        if entry.msgid_plural:
            return tuple(sorted(
                (idx, str(text or "")) for idx, text in entry.msgstr_plural.items()
            ))
        return str(entry.msgstr or "")

    def _translation_key(self, entry):
        """Clave para comparar traducciones. None si la entrada no tiene texto."""
        if not self._has_translation_text(entry):
            return None
        if entry.msgid_plural:
            return ("plural", tuple(
                (idx, str(text or "").strip())
                for idx, text in sorted(entry.msgstr_plural.items())
            ))
        return ("singular", str(entry.msgstr or "").strip())

    def _inconsistent_groups(self):
        """MsgId repetidos que tienen más de una traducción distinta."""
        by_msgid: Dict[str, List[int]] = {}
        for index, entry in enumerate(self.entries):
            if entry.msgid:
                by_msgid.setdefault(entry.msgid, []).append(index)
        groups = []
        for msgid, indices in by_msgid.items():
            variants: Dict[tuple, List[int]] = {}
            for index in indices:
                key = self._translation_key(self.entries[index])
                if key is None:
                    continue
                variants.setdefault(key, []).append(index)
            if len(variants) < 2:
                continue
            groups.append({
                "msgid": msgid,
                "indices": indices,
                "variants": [
                    {"source_index": members[0], "indices": members}
                    for members in variants.values()
                ],
            })
        return groups

    def _remember_review(self, index: int):
        if index not in self.entry_metadata:
            self.entry_metadata[index] = {}
        self.entry_metadata[index]["needs_review"] = True

    def _propagate_to_same_msgid(self, source_index: int, only_empty: bool = False) -> int:
        """Copia la traducción de una entrada al resto con el mismo msgid."""
        if source_index < 0 or source_index >= len(self.entries):
            return 0
        source = self.entries[source_index]
        if not source.msgid or not self._has_translation_text(source):
            return 0
        source_key = self._translation_key(source)
        speaker = self.extract_speaker_from_metadata(source) or ""
        copied = 0
        for index, entry in enumerate(self.entries):
            if index == source_index or entry.msgid != source.msgid:
                continue
            has_text = self._has_translation_text(entry)
            if only_empty and has_text:
                continue
            if has_text and self._translation_key(entry) == source_key:
                continue
            self._apply_copied_translation(entry, source)
            if index not in self.entry_metadata:
                self.entry_metadata[index] = {}
            self.entry_metadata[index]["copied_from"] = {
                "index": source_index,
                "speaker": speaker,
            }
            copied += 1
        return copied

    def _translation_preview(self, entry, limit: int = 160) -> str:
        if entry.msgid_plural:
            lines = [
                f"[{idx}]: {text}"
                for idx, text in sorted(entry.msgstr_plural.items())
                if str(text or "").strip()
            ]
            text = " | ".join(lines)
        else:
            text = str(entry.msgstr or "").strip()
        text = " ".join(text.split())
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def show_inconsistencies(self):
        """Vista para elegir una traducción cuando el mismo MsgId tiene varias."""
        if not self.entries:
            messagebox.showinfo("Inconsistencias", "No hay archivo cargado.")
            return
        existing = getattr(self, "inconsistency_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            self._refresh_inconsistency_view()
            return
        
        window = tk.Toplevel(self.root)
        window.title("Mismo texto, traducciones distintas")
        window.geometry("980x680")
        window.transient(self.root)
        self.inconsistency_window = window
        window.protocol("WM_DELETE_WINDOW", window.destroy)
        
        ttk.Label(
            window,
            text="Elige la traducción buena. Se copiará en todas las entradas con el mismo texto original, incluidas las que estén vacías.",
            wraplength=940,
        ).pack(fill=tk.X, padx=10, pady=(10, 4))
        
        paned = ttk.PanedWindow(window, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        
        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=2)
        
        columns = ("variantes", "entradas", "msgid")
        self.inconsistency_tree = ttk.Treeview(left, columns=columns, show="headings", height=18)
        self.inconsistency_tree.heading("variantes", text="Variantes")
        self.inconsistency_tree.heading("entradas", text="Entradas")
        self.inconsistency_tree.heading("msgid", text="MsgId")
        self.inconsistency_tree.column("variantes", width=80, stretch=False)
        self.inconsistency_tree.column("entradas", width=80, stretch=False)
        self.inconsistency_tree.column("msgid", width=280)
        tree_scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.inconsistency_tree.yview)
        self.inconsistency_tree.configure(yscrollcommand=tree_scroll.set)
        self.inconsistency_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.inconsistency_tree.bind("<<TreeviewSelect>>", self._on_inconsistency_group_select)
        
        ttk.Label(right, text="Texto original").pack(anchor=tk.W)
        self.inconsistency_msgid = scrolledtext.ScrolledText(right, height=5, wrap=tk.WORD, state=tk.DISABLED)
        self.inconsistency_msgid.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Label(right, text="Traducciones distintas").pack(anchor=tk.W)
        self.inconsistency_variants = tk.Listbox(right, height=6, activestyle="dotbox")
        self.inconsistency_variants.pack(fill=tk.X, pady=(0, 6))
        self.inconsistency_variants.bind("<<ListboxSelect>>", self._on_inconsistency_variant_select)
        
        self.inconsistency_variant_text = scrolledtext.ScrolledText(right, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.inconsistency_variant_text.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        
        self.inconsistency_entries_label = ttk.Label(right, text="", wraplength=560)
        self.inconsistency_entries_label.pack(anchor=tk.W, pady=(0, 6))
        
        actions = ttk.Frame(right)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="Ver entrada", command=self._show_selected_inconsistency_entry).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            actions,
            text="Usar esta traducción en todas",
            command=self._apply_selected_inconsistency,
        ).pack(side=tk.LEFT)
        
        self._refresh_inconsistency_view()

    def _refresh_inconsistency_view(self):
        window = getattr(self, "inconsistency_window", None)
        if window is None or not window.winfo_exists():
            self.update_statistics()
            return
        self._inconsistency_groups_cache = self._inconsistent_groups()
        self.inconsistency_tree.delete(*self.inconsistency_tree.get_children())
        for position, group in enumerate(self._inconsistency_groups_cache):
            preview = group["msgid"].replace("\n", " ")
            if len(preview) > 80:
                preview = preview[:80] + "..."
            self.inconsistency_tree.insert(
                "",
                tk.END,
                iid=str(position),
                values=(len(group["variants"]), len(group["indices"]), preview),
            )
        self._clear_inconsistency_detail()
        if self._inconsistency_groups_cache:
            first = self.inconsistency_tree.get_children()[0]
            self.inconsistency_tree.selection_set(first)
            self.inconsistency_tree.focus(first)
            self._on_inconsistency_group_select(None)
        else:
            self.inconsistency_entries_label.config(
                text="No hay textos originales con traducciones distintas."
            )
        self.update_statistics()

    def _clear_inconsistency_detail(self):
        self.inconsistency_msgid.config(state=tk.NORMAL)
        self.inconsistency_msgid.delete(1.0, tk.END)
        self.inconsistency_msgid.config(state=tk.DISABLED)
        self.inconsistency_variants.delete(0, tk.END)
        self.inconsistency_variant_text.config(state=tk.NORMAL)
        self.inconsistency_variant_text.delete(1.0, tk.END)
        self.inconsistency_variant_text.config(state=tk.DISABLED)
        self.inconsistency_entries_label.config(text="")

    def _selected_inconsistency_group(self):
        selection = self.inconsistency_tree.selection()
        if not selection:
            return None
        position = int(selection[0])
        groups = getattr(self, "_inconsistency_groups_cache", [])
        if position < 0 or position >= len(groups):
            return None
        return groups[position]

    def _selected_inconsistency_variant(self):
        group = self._selected_inconsistency_group()
        if group is None:
            return None, None
        selection = self.inconsistency_variants.curselection()
        if not selection:
            return group, None
        variant_index = selection[0]
        if variant_index >= len(group["variants"]):
            return group, None
        return group, group["variants"][variant_index]

    def _on_inconsistency_group_select(self, event):
        group = self._selected_inconsistency_group()
        self._clear_inconsistency_detail()
        if group is None:
            return
        self.inconsistency_msgid.config(state=tk.NORMAL)
        self.inconsistency_msgid.insert(1.0, group["msgid"])
        self.inconsistency_msgid.config(state=tk.DISABLED)
        for variant in group["variants"]:
            entry = self.entries[variant["source_index"]]
            preview = self._translation_preview(entry)
            self.inconsistency_variants.insert(
                tk.END,
                f"{len(variant['indices'])} entradas — {preview}",
            )
        self.inconsistency_variants.selection_set(0)
        self._on_inconsistency_variant_select(None)

    def _on_inconsistency_variant_select(self, event):
        group, variant = self._selected_inconsistency_variant()
        self.inconsistency_variant_text.config(state=tk.NORMAL)
        self.inconsistency_variant_text.delete(1.0, tk.END)
        if variant is None:
            self.inconsistency_variant_text.config(state=tk.DISABLED)
            self.inconsistency_entries_label.config(text="")
            return
        source = self.entries[variant["source_index"]]
        if source.msgid_plural:
            lines = [f"[{idx}]: {text}" for idx, text in sorted(source.msgstr_plural.items())]
            shown = "\n".join(lines)
        else:
            shown = str(source.msgstr or "")
        self.inconsistency_variant_text.insert(1.0, shown)
        self.inconsistency_variant_text.config(state=tk.DISABLED)
        numbers = ", ".join(f"#{index + 1}" for index in variant["indices"][:12])
        if len(variant["indices"]) > 12:
            numbers += f" y {len(variant['indices']) - 12} más"
        self.inconsistency_entries_label.config(text=f"Entradas con esta traducción: {numbers}")

    def _show_selected_inconsistency_entry(self):
        _group, variant = self._selected_inconsistency_variant()
        if variant is None:
            return
        self._select_entry_by_index(variant["source_index"])

    def _select_entry_by_index(self, index: int):
        if index < 0 or index >= len(self.entries):
            return
        for item in self.entries_tree.get_children():
            values = self.entries_tree.item(item)["values"]
            if values and int(values[0]) - 1 == index:
                self.entries_tree.selection_set(item)
                self.entries_tree.see(item)
                self.on_entry_select(None)
                return
        self.current_entry_index = index
        self.display_entry(self.entries[index])

    def _apply_selected_inconsistency(self):
        _group, variant = self._selected_inconsistency_variant()
        if variant is None:
            messagebox.showwarning("Inconsistencias", "Elige una traducción.", parent=self.inconsistency_window)
            return
        source_index = variant["source_index"]
        msgid = self.entries[source_index].msgid
        others = sum(1 for entry in self.entries if entry.msgid == msgid) - 1
        if others <= 0:
            return
        confirmed = messagebox.askyesno(
            "Aplicar traducción",
            f"Se copiará esta traducción en las otras {others} entradas con el mismo texto original.\n\n"
            "Las que ya tenían otra traducción quedarán igual que esta.",
            parent=self.inconsistency_window,
        )
        if not confirmed:
            return
        copied = self._propagate_to_same_msgid(source_index, only_empty=False)
        self.has_unsaved_changes = True
        self.update_window_title()
        self.update_entries_list()
        self._refresh_current_entry_display()
        self.status_bar.config(text=f"Traducción unificada en {copied} entradas")
        self._refresh_inconsistency_view()

    def _apply_copied_translation(self, entry, source_entry):
        """Copia el texto traducido de una entrada a otra."""
        if not entry.msgid_plural:
            if source_entry.msgid_plural:
                text = source_entry.msgstr_plural.get(0) or source_entry.msgstr or ""
            else:
                text = source_entry.msgstr or ""
            entry.msgstr = str(text)
            return
        entry.msgstr = ""
        source_plurals = dict(source_entry.msgstr_plural) if source_entry.msgid_plural else {}
        if not source_plurals and str(source_entry.msgstr or "").strip():
            source_plurals = {0: str(source_entry.msgstr)}
        if not entry.msgstr_plural:
            entry.msgstr_plural[0] = str(source_plurals.get(0, ""))
            entry.msgstr_plural[1] = str(source_plurals.get(1, source_plurals.get(0, "")))
        else:
            for idx in list(entry.msgstr_plural.keys()):
                if idx in source_plurals:
                    entry.msgstr_plural[idx] = str(source_plurals[idx] or "")
                elif source_plurals:
                    fallback = source_plurals.get(1, source_plurals.get(0, ""))
                    entry.msgstr_plural[idx] = str(fallback or "")

    def _build_translator_chain(self) -> List[Tuple[str, object, Optional[int]]]:
        """Motores en orden: DeepL (si hay clave), Google y MyMemory."""
        chain = []
        deepl_key = self.deepl_key_var.get().strip()
        if deepl_key:
            source = self.engine_lang_codes["deepl"].get(self.source_lang)
            target = self.engine_lang_codes["deepl"].get(self.target_lang)
            if source and target:
                try:
                    chain.append((
                        "DeepL",
                        DeeplTranslator(
                            api_key=deepl_key,
                            source=source,
                            target=target,
                            use_free_api=deepl_key.endswith(":fx"),
                        ),
                        None,
                    ))
                except Exception as e:
                    print(f"DeepL no disponible: {e}")

        source = self.engine_lang_codes["google"].get(self.source_lang)
        target = self.engine_lang_codes["google"].get(self.target_lang)
        if source and target:
            try:
                chain.append(("Google", GoogleTranslator(source=source, target=target), 5000))
            except Exception as e:
                print(f"Google no disponible: {e}")

        source = self.engine_lang_codes["mymemory"].get(self.source_lang)
        target = self.engine_lang_codes["mymemory"].get(self.target_lang)
        if source and target:
            try:
                chain.append(("MyMemory", MyMemoryTranslator(source=source, target=target), 500))
            except Exception as e:
                print(f"MyMemory no disponible: {e}")
        return chain

    def _translate_text(self, text: str, chain, disabled: set) -> Tuple[str, str]:
        """Traduce un texto con el primer motor que responda."""
        errors = []
        for name, translator, limit in chain:
            if name in disabled:
                continue
            if limit is not None and len(text) > limit:
                errors.append(f"{name}: el texto supera {limit} caracteres")
                continue
            try:
                translated = translator.translate(text)
                if not translated or not str(translated).strip():
                    raise RuntimeError("respuesta vacía")
                return str(translated), name
            except Exception as e:
                errors.append(f"{name}: {e}")
                message = str(e).lower()
                if "too many requests" in message or "429" in message:
                    disabled.add(name)
        detail = "\n".join(errors) if errors else "No hay ningún motor disponible para este par de idiomas."
        raise RuntimeError(detail)

    def _store_translation(self, entry, singular: str, plural: Optional[str] = None):
        """Guarda una traducción. En plurales rellena msgstr_plural, no msgstr."""
        singular = str(singular or "")
        if entry.msgid_plural:
            entry.msgstr = ""
            if not entry.msgstr_plural:
                entry.msgstr_plural[0] = singular
                entry.msgstr_plural[1] = str(plural or "")
                return
            for idx in list(entry.msgstr_plural.keys()):
                if idx == 0:
                    entry.msgstr_plural[idx] = singular
                else:
                    entry.msgstr_plural[idx] = str(plural if plural is not None else singular)
        else:
            entry.msgstr = singular

    def _format_translation_for_editor(self, entry, singular: str, plural: Optional[str] = None) -> str:
        """Texto que el editor espera en el cuadro de traducción."""
        if not entry.msgid_plural:
            return str(singular or "")
        lines = [f"[0]: {singular or ''}"]
        lines.append(f"[1]: {plural or ''}")
        for idx in sorted(entry.msgstr_plural.keys()):
            if idx not in (0, 1):
                lines.append(f"[{idx}]: {entry.msgstr_plural.get(idx, '')}")
        return "\n".join(lines)

    def translate_current(self):
        """Traduce la entrada actual"""
        if self.current_entry_index is None:
            messagebox.showwarning("Advertencia", "No hay entrada seleccionada.")
            return
        
        if self.is_processing:
            messagebox.showwarning("Advertencia", "Ya hay una operación en progreso.")
            return
        
        entry = self.entries[self.current_entry_index]
        text_to_translate = entry.msgid
        
        if not text_to_translate:
            messagebox.showwarning("Advertencia", "No hay texto para traducir.")
            return
        
        self.is_processing = True
        self.status_bar.config(text="Traduciendo...")
        
        def translate_thread():
            try:
                chain = self._build_translator_chain()
                disabled = set()
                singular, engine = self._translate_text(text_to_translate, chain, disabled)
                plural = None
                if entry.msgid_plural:
                    plural, plural_engine = self._translate_text(entry.msgid_plural, chain, disabled)
                    engine = plural_engine
                translated_text = self._format_translation_for_editor(entry, singular, plural)
                current_idx = self.current_entry_index

                def apply_translation():
                    self.msgstr_text.delete(1.0, tk.END)
                    if translated_text:
                        self.msgstr_text.insert(1.0, translated_text)
                    self.on_translation_changed()
                    copied = 0
                    if translated_text.strip() and current_idx is not None:
                        copied = self._propagate_to_same_msgid(current_idx, only_empty=True)
                        self._mark_entry_for_review(current_idx)
                    extra = f", copiada en {copied} entradas iguales" if copied else ""
                    self.status_bar.config(text=f"Traducción completada ({engine}){extra}")

                self.root.after(0, apply_translation)
            except Exception as e:
                error_text = str(e)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error al traducir:\n{error_text}"))
                self.root.after(0, lambda: self.status_bar.config(text="Error al traducir"))
            finally:
                self.is_processing = False
        
        thread = threading.Thread(target=translate_thread, daemon=True)
        thread.start()
    
    def correct_current(self):
        """Corrige la traducción actual usando LanguageTool"""
        if not LANGUAGE_TOOL_AVAILABLE:
            messagebox.showwarning(
                "Advertencia", 
                "LanguageTool no está disponible.\n\n"
                "Por favor, instala language-tool-python:\n"
                "pip install language-tool-python"
            )
            return
        
        # Si no hay índice actual, intentar obtenerlo de la selección del treeview
        if self.current_entry_index is None:
            selection = self.entries_tree.selection()
            if selection:
                item = selection[0]
                values = self.entries_tree.item(item)['values']
                if values:
                    self.current_entry_index = int(values[0]) - 1
        
        if self.current_entry_index is None or self.current_entry_index < 0 or self.current_entry_index >= len(self.entries):
            messagebox.showwarning("Advertencia", "No hay entrada seleccionada.")
            return
        
        text_to_correct = self.msgstr_text.get(1.0, tk.END).strip()
        
        if not text_to_correct:
            messagebox.showwarning("Advertencia", "No hay texto para corregir.")
            return
        
        if self.is_processing:
            messagebox.showwarning("Advertencia", "Ya hay una operación en progreso.")
            return
        
        self.is_processing = True
        self.status_bar.config(text="Corrigiendo...")
        
        def correct_thread():
            try:
                # Obtener código de idioma para LanguageTool
                lang_code = self.language_tool_codes.get(self.target_lang, "ca")
                
                # Reinicializar LanguageTool con el idioma correcto
                try:
                    tool = language_tool_python.LanguageTool(lang_code)
                except Exception as e:
                    # Si falla, intentar con catalán por defecto
                    try:
                        tool = language_tool_python.LanguageTool('ca')
                    except:
                        raise Exception(f"No se pudo inicializar LanguageTool: {str(e)}")
                
                # Corregir el texto
                matches = tool.check(text_to_correct)
                
                if not matches:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Corrección completada", 
                        "No se encontraron errores en el texto."
                    ))
                    self.root.after(0, lambda: self.status_bar.config(text="Sin errores encontrados"))
                else:
                    # Aplicar correcciones automáticas
                    corrected_text = language_tool_python.utils.correct(text_to_correct, matches)
                    
                    # Mostrar información de errores encontrados
                    errors_info = []
                    for match in matches[:10]:  # Mostrar máximo 10 errores
                        error_msg = match.message
                        error_context = match.context
                        errors_info.append(f"• {error_msg}\n  Contexto: {error_context}")
                    
                    if len(matches) > 10:
                        errors_info.append(f"\n... y {len(matches) - 10} errores más")
                    
                    # Actualizar el texto corregido
                    corrected_text_str = str(corrected_text) if corrected_text else ""
                    self.root.after(0, lambda: self.msgstr_text.delete(1.0, tk.END))
                    self.root.after(0, lambda t=corrected_text_str: self.msgstr_text.insert(1.0, t) if t else None)
                    self.root.after(0, self.on_translation_changed)
                    
                    # Mostrar información de errores
                    errors_text = "\n".join(errors_info)
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Corrección completada",
                        f"Se encontraron {len(matches)} error(es) y se aplicaron correcciones automáticas.\n\n"
                        f"Errores encontrados:\n{errors_text}"
                    ))
                    self.root.after(0, lambda: self.status_bar.config(
                        text=f"Corrección completada: {len(matches)} error(es) corregido(s)"
                    ))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", 
                    f"Error al corregir el texto:\n{str(e)}"
                ))
                self.root.after(0, lambda: self.status_bar.config(text="Error en la corrección"))
            finally:
                self.is_processing = False
        
        thread = threading.Thread(target=correct_thread, daemon=True)
        thread.start()
    
    def _mark_entry_for_review(self, entry_index: int):
        """Marca una entrada como 'a revisar'"""
        print(f"\n[DEBUG _mark_entry_for_review] INICIO - entry_index: {entry_index}, current_entry_index: {self.current_entry_index}")
        if entry_index is not None and 0 <= entry_index < len(self.entries):
            if entry_index not in self.entry_metadata:
                self.entry_metadata[entry_index] = {}
            self.entry_metadata[entry_index]['needs_review'] = True
            print(f"[DEBUG _mark_entry_for_review] Marcado entry_metadata[{entry_index}]: {self.entry_metadata[entry_index]}")
            # Actualizar lista primero
            self.update_entries_list()
            # Actualizar el checkbox y display si es la entrada actual
            if entry_index == self.current_entry_index:
                print(f"[DEBUG _mark_entry_for_review] Es la entrada actual, actualizando checkbox")
                self.needs_review_var.set(True)
                # Forzar actualización del display para mostrar los botones
                self.display_entry(self.entries[entry_index])
        else:
            print(f"[DEBUG _mark_entry_for_review] ERROR: entry_index inválido o fuera de rango")
        print(f"[DEBUG _mark_entry_for_review] FIN\n")
    
    def _refresh_current_entry_display(self):
        """Actualiza el display de la entrada actual si está seleccionada"""
        if self.current_entry_index is not None and 0 <= self.current_entry_index < len(self.entries):
            self.display_entry(self.entries[self.current_entry_index])
    
    def clear_current_translation(self):
        """Limpia la traducción actual"""
        self.msgstr_text.delete(1.0, tk.END)
        self.on_translation_changed(None)
    
    def toggle_needs_review(self):
        """Marca o desmarca la entrada actual como 'a revisar'"""
        print(f"\n[DEBUG toggle_needs_review] INICIO - current_entry_index: {self.current_entry_index}")
        if self.current_entry_index is None:
            print("[DEBUG toggle_needs_review] ERROR: current_entry_index es None, saliendo")
            return
        
        needs_review = self.needs_review_var.get()
        print(f"[DEBUG toggle_needs_review] needs_review checkbox: {needs_review}")
        print(f"[DEBUG toggle_needs_review] entry_metadata ANTES: {self.entry_metadata.get(self.current_entry_index, {})}")
        
        if needs_review:
            # Marcar como "a revisar"
            print(f"[DEBUG toggle_needs_review] MARCANDO como 'a revisar'")
            if self.current_entry_index not in self.entry_metadata:
                self.entry_metadata[self.current_entry_index] = {}
            self.entry_metadata[self.current_entry_index]['needs_review'] = True
        else:
            # Desmarcar "a revisar"
            print(f"[DEBUG toggle_needs_review] DESMARCANDO 'a revisar'")
            if self.current_entry_index in self.entry_metadata:
                # Eliminar needs_review
                if 'needs_review' in self.entry_metadata[self.current_entry_index]:
                    print(f"[DEBUG toggle_needs_review] Eliminando 'needs_review' de metadata")
                    del self.entry_metadata[self.current_entry_index]['needs_review']
                
                # Si no hay copied_from, eliminar toda la entrada de metadata
                # Si hay copied_from, mantenerlo (puede ser útil para referencia)
                if not self.entry_metadata[self.current_entry_index].get('copied_from'):
                    print(f"[DEBUG toggle_needs_review] No hay 'copied_from', eliminando toda la entrada de metadata")
                    del self.entry_metadata[self.current_entry_index]
                else:
                    print(f"[DEBUG toggle_needs_review] Hay 'copied_from', manteniendo entrada sin 'needs_review'")
                # Si hay copied_from, mantener la entrada pero sin needs_review
        
        print(f"[DEBUG toggle_needs_review] entry_metadata DESPUÉS: {self.entry_metadata.get(self.current_entry_index, {})}")
        
        # Actualizar display para reflejar cambios
        self.display_entry(self.entries[self.current_entry_index])
        
        # Actualizar lista
        self.update_entries_list()
        self.has_unsaved_changes = True
        self.update_window_title()
        print(f"[DEBUG toggle_needs_review] FIN\n")
    
    def mark_as_okay(self):
        """Marca la entrada actual como 'okay' (desmarca 'a revisar') y salta a la siguiente"""
        print(f"\n[DEBUG mark_as_okay] INICIO - current_entry_index: {self.current_entry_index}")
        
        # Si current_entry_index es None, intentar obtenerlo de la selección del treeview
        if self.current_entry_index is None:
            print("[DEBUG mark_as_okay] current_entry_index es None, intentando obtener de selección del treeview")
            selection = self.entries_tree.selection()
            if selection:
                item = selection[0]
                values = self.entries_tree.item(item)['values']
                if values:
                    self.current_entry_index = int(values[0]) - 1
                    print(f"[DEBUG mark_as_okay] current_entry_index obtenido de treeview: {self.current_entry_index}")
        
        if self.current_entry_index is None:
            print("[DEBUG mark_as_okay] ERROR: current_entry_index es None después de intentar obtenerlo, saliendo")
            return
        
        # Guardar el índice actual antes de desmarcar
        current_idx = self.current_entry_index
        print(f"[DEBUG mark_as_okay] Índice actual: {current_idx}")
        print(f"[DEBUG mark_as_okay] entry_metadata ANTES: {self.entry_metadata.get(current_idx, {})}")
        
        # Desmarcar "a revisar" y limpiar metadata
        self.needs_review_var.set(False)
        print(f"[DEBUG mark_as_okay] Checkbox desmarcado, llamando toggle_needs_review()")
        self.toggle_needs_review()
        print(f"[DEBUG mark_as_okay] entry_metadata DESPUÉS de toggle: {self.entry_metadata.get(current_idx, {})}")
        print(f"[DEBUG mark_as_okay] current_entry_index DESPUÉS de toggle: {self.current_entry_index}")
        
        # Asegurar que current_entry_index se mantiene después de toggle_needs_review
        if self.current_entry_index != current_idx:
            print(f"[DEBUG mark_as_okay] WARNING: current_entry_index cambió de {current_idx} a {self.current_entry_index}, restaurando")
            self.current_entry_index = current_idx
        
        # Actualizar la lista y estadísticas
        self.update_entries_list()
        
        # Asegurar que current_entry_index se mantiene después de update_entries_list
        if self.current_entry_index != current_idx:
            print(f"[DEBUG mark_as_okay] WARNING: current_entry_index cambió después de update_entries_list, restaurando")
            self.current_entry_index = current_idx
        
        # Buscar la siguiente entrada "a revisar" empezando desde la siguiente a la actual
        start_index = current_idx + 1
        found = False
        
        # Buscar desde la siguiente hasta el final
        for i in range(start_index, len(self.entries)):
            if self.entry_metadata.get(i, {}).get('needs_review', False):
                # Seleccionar en el tree
                for item in self.entries_tree.get_children():
                    values = self.entries_tree.item(item)['values']
                    if values and int(values[0]) - 1 == i:
                        self.entries_tree.selection_set(item)
                        self.entries_tree.see(item)
                        self.on_entry_select(None)
                        found = True
                        return
        
        # Si no hay más desde aquí, buscar desde el inicio
        for i in range(0, start_index):
            if self.entry_metadata.get(i, {}).get('needs_review', False):
                # Seleccionar en el tree
                for item in self.entries_tree.get_children():
                    values = self.entries_tree.item(item)['values']
                    if values and int(values[0]) - 1 == i:
                        self.entries_tree.selection_set(item)
                        self.entries_tree.see(item)
                        self.on_entry_select(None)
                        found = True
                        return
        
        # Si no hay más entradas "a revisar", mostrar mensaje
        if not found:
            messagebox.showinfo("Completado", "No hay más entradas marcadas como 'a revisar'.")
    
    def next_untranslated(self):
        """Navega a la siguiente entrada sin traducir"""
        if self.current_entry_index is None:
            start_index = 0
        else:
            start_index = self.current_entry_index + 1
        
        # Buscar desde la siguiente hasta el final
        for i in range(start_index, len(self.entries)):
            if not self.entries[i].translated():
                # Seleccionar en el tree
                for item in self.entries_tree.get_children():
                    values = self.entries_tree.item(item)['values']
                    if values and int(values[0]) - 1 == i:
                        self.entries_tree.selection_set(item)
                        self.entries_tree.see(item)
                        self.on_entry_select(None)
                        return
        
        # Si no hay más desde aquí, buscar desde el inicio
        for i in range(0, start_index):
            if not self.entries[i].translated():
                # Seleccionar en el tree
                for item in self.entries_tree.get_children():
                    values = self.entries_tree.item(item)['values']
                    if values and int(values[0]) - 1 == i:
                        self.entries_tree.selection_set(item)
                        self.entries_tree.see(item)
                        self.on_entry_select(None)
                        return
        
        messagebox.showinfo("Completado", "No hay más entradas sin traducir.")
    
    def next_needs_review(self):
        """Navega a la siguiente entrada marcada como 'a revisar'"""
        if self.current_entry_index is None:
            start_index = 0
        else:
            start_index = self.current_entry_index + 1
        
        # Buscar desde la siguiente hasta el final
        for i in range(start_index, len(self.entries)):
            if self.entry_metadata.get(i, {}).get('needs_review', False):
                # Seleccionar en el tree
                for item in self.entries_tree.get_children():
                    values = self.entries_tree.item(item)['values']
                    if values and int(values[0]) - 1 == i:
                        self.entries_tree.selection_set(item)
                        self.entries_tree.see(item)
                        self.on_entry_select(None)
                        return
        
        # Si no hay más desde aquí, buscar desde el inicio
        for i in range(0, start_index):
            if self.entry_metadata.get(i, {}).get('needs_review', False):
                # Seleccionar en el tree
                for item in self.entries_tree.get_children():
                    values = self.entries_tree.item(item)['values']
                    if values and int(values[0]) - 1 == i:
                        self.entries_tree.selection_set(item)
                        self.entries_tree.see(item)
                        self.on_entry_select(None)
                        return
        
        messagebox.showinfo("Completado", "No hay más entradas marcadas como 'a revisar'.")
    
    def pretranslate_all(self):
        """Pretraduce todas las entradas sin traducir usando DeepL o Google"""
        if not self.po_file:
            messagebox.showwarning("Advertencia", "No hay archivo cargado.")
            return
        
        if self.is_processing:
            messagebox.showwarning("Advertencia", "Ya hay una operación en progreso.")
            return
        
        response = messagebox.askyesno(
            "Confirmar",
            "¿Pretraducir las entradas que todavía no tienen texto?\n\n"
            "Cada texto original se traduce una sola vez y se copia en las demás entradas vacías.\n"
            "Las que ya tienen traducción, incluidas las fuzzy, no se modifican.\n"
            "Puede tardar varios minutos."
        )
        if not response:
            return
        
        self.is_processing = True
        self.status_bar.config(text="Pretraduciendo...")
        
        thread = threading.Thread(target=self._pretranslate_all_thread, daemon=True)
        thread.start()
    
    def _pretranslate_all_thread(self):
        """Hilo para pretraducir todas las entradas"""
        try:
            chain = self._build_translator_chain()
            if not chain:
                raise RuntimeError(
                    "No hay ningún motor disponible para este par de idiomas.\n"
                    "Catalán no está disponible en DeepL con la versión instalada de deep-translator. "
                    "Sin clave de DeepL se usan Google y, si Google bloquea la petición, MyMemory."
                )
            disabled = set()
            engines_used = set()
            translated_count = 0
            error_count = 0
            pending_by_msgid: Dict[str, List[int]] = {}
            for i, entry in enumerate(self.entries):
                if entry.msgid and not self._has_translation_text(entry):
                    pending_by_msgid.setdefault(entry.msgid, []).append(i)
            
            for msgid, indices in pending_by_msgid.items():
                try:
                    existing = next(
                        (
                            index for index, entry in enumerate(self.entries)
                            if entry.msgid == msgid and self._has_translation_text(entry)
                        ),
                        None,
                    )
                    if existing is None:
                        entry = self.entries[indices[0]]
                        singular, engine = self._translate_text(entry.msgid, chain, disabled)
                        plural = None
                        if entry.msgid_plural:
                            plural, plural_engine = self._translate_text(entry.msgid_plural, chain, disabled)
                            engines_used.add(plural_engine)
                        if not singular or not singular.strip():
                            continue
                        self._store_translation(entry, singular, plural)
                        engines_used.add(engine)
                        existing = indices[0]
                    self._propagate_to_same_msgid(existing, only_empty=True)
                    for index in indices:
                        self._remember_review(index)
                    translated_count += len(indices)
                    if translated_count and translated_count % 10 == 0:
                        self.root.after(0, lambda count=translated_count: self.status_bar.config(
                            text=f"Pretraduciendo... {count} traducidas"))
                except Exception as e:
                    error_count += 1
                    print(f"Error traduciendo '{msgid[:40]}': {str(e)}")
            
            self.root.after(0, self.update_entries_list)
            self.root.after(0, lambda: setattr(self, 'has_unsaved_changes', True))
            self.root.after(0, self.update_window_title)
            
            # Actualizar display de entrada actual si está seleccionada
            self.root.after(0, lambda: self._refresh_current_entry_display())

            engines_text = ", ".join(sorted(engines_used)) if engines_used else "ninguno"
            summary = (
                f"Pretraducción completada.\n{translated_count} entradas traducidas.\n"
                f"{error_count} errores.\nMotores: {engines_text}"
            )
            status = f"Pretraducción completada: {translated_count} traducidas, {error_count} errores ({engines_text})"
            self.root.after(0, lambda text=status: self.status_bar.config(text=text))
            self.root.after(0, lambda text=summary: messagebox.showinfo("Completado", text))
        
        except Exception as e:
            error_text = str(e)
            self.root.after(0, lambda msg=error_text: messagebox.showerror(
                "Error", f"Error durante la pretraducción:\n{msg}"))
        finally:
            self.is_processing = False
    
    def copy_translations(self):
        """Copia traducciones de entradas con msgid idéntico o similar"""
        if not self.po_file:
            messagebox.showwarning("Advertencia", "No hay archivo cargado.")
            return
        
        if self.is_processing:
            messagebox.showwarning("Advertencia", "Ya hay una operación en progreso.")
            return
        
        mode = self.copy_mode_var.get()
        mark_for_review = self.copy_mark_review_var.get()
        
        self.is_processing = True
        self.status_bar.config(text="Copiando traducciones...")
        
        thread = threading.Thread(target=self._copy_translations_thread, args=(mode, mark_for_review), daemon=True)
        thread.start()
    
    def _copy_translations_thread(self, mode: str, mark_for_review: bool):
        """Hilo para copiar traducciones"""
        try:
            copied_count = 0
            
            if mode == "identical":
                # Agrupar entradas por MsgId idéntico
                # {msgid: [{'index': int, 'entry': entry, 'has_translation': bool}]}
                msgid_groups: Dict[str, List[Dict]] = {}
                
                for idx, entry in enumerate(self.entries):
                    if entry.msgid:
                        msgid = entry.msgid
                        if msgid not in msgid_groups:
                            msgid_groups[msgid] = []
                        
                        # Verificar si tiene traducción (no None y no vacío)
                        has_translation = entry.translated() and entry.msgstr and str(entry.msgstr).strip()
                        
                        msgid_groups[msgid].append({
                            'index': idx,
                            'entry': entry,
                            'has_translation': has_translation
                        })
                
                # Para cada grupo de MsgId idénticos
                for msgid, group in msgid_groups.items():
                    # Encontrar la primera entrada con traducción
                    source_entry = None
                    source_index = None
                    source_speaker = None
                    
                    for item in group:
                        if item['has_translation']:
                            source_entry = item['entry']
                            source_index = item['index']
                            source_speaker = self.extract_speaker_from_metadata(source_entry)
                            break
                    
                    # Si encontramos una fuente con traducción, copiar a todas las que no tienen
                    if source_entry and source_entry.msgstr:
                        source_msgstr = str(source_entry.msgstr).strip()
                        if source_msgstr:  # Solo copiar si tiene contenido
                            for item in group:
                                if not item['has_translation']:
                                    entry = item['entry']
                                    entry.msgstr = source_msgstr
                                    
                                    # Guardar información de copia
                                    idx = item['index']
                                    if idx not in self.entry_metadata:
                                        self.entry_metadata[idx] = {}
                                    self.entry_metadata[idx]['copied_from'] = {
                                        'index': source_index,
                                        'speaker': source_speaker or ''
                                    }
                                    
                                    # Marcar como "a revisar" solo si la opción está activada
                                    if mark_for_review:
                                        self.entry_metadata[idx]['needs_review'] = True
                                    
                                    copied_count += 1
                    
                    # Actualizar progreso cada 10 entradas
                    if copied_count % 10 == 0:
                        self.root.after(0, lambda count=copied_count: self.status_bar.config(
                            text=f"Copiando traducciones... {count} copiadas"))
            
            elif mode == "to_review":
                # Copia la traducción ya aceptada a las marcadas a revisar con el mismo msgid.
                msgid_groups: Dict[str, List[Dict]] = {}
                for idx, entry in enumerate(self.entries):
                    if not entry.msgid:
                        continue
                    msgid_groups.setdefault(entry.msgid, []).append({
                        'index': idx,
                        'entry': entry,
                    })
                
                for group in msgid_groups.values():
                    source_item = None
                    for item in group:
                        entry = item['entry']
                        needs_review = self.entry_metadata.get(item['index'], {}).get('needs_review', False)
                        if not needs_review and self._has_translation_text(entry):
                            source_item = item
                            break
                    if source_item is None:
                        continue
                    
                    source_entry = source_item['entry']
                    source_index = source_item['index']
                    source_speaker = self.extract_speaker_from_metadata(source_entry)
                    for item in group:
                        if item['index'] == source_index:
                            continue
                        needs_review = self.entry_metadata.get(item['index'], {}).get('needs_review', False)
                        if not needs_review:
                            continue
                        entry = item['entry']
                        before = self._translation_snapshot(entry)
                        self._apply_copied_translation(entry, source_entry)
                        changed = before != self._translation_snapshot(entry)
                        idx = item['index']
                        if idx not in self.entry_metadata:
                            self.entry_metadata[idx] = {}
                        self.entry_metadata[idx]['copied_from'] = {
                            'index': source_index,
                            'speaker': source_speaker or ''
                        }
                        if mark_for_review:
                            self.entry_metadata[idx]['needs_review'] = True
                        elif 'needs_review' in self.entry_metadata[idx]:
                            del self.entry_metadata[idx]['needs_review']
                            changed = True
                        if changed:
                            copied_count += 1
                            if copied_count % 10 == 0:
                                self.root.after(0, lambda count=copied_count: self.status_bar.config(
                                    text=f"Copiando traducciones... {count} copiadas"))
            
            else:  # similar
                # Crear índice de traducciones existentes con información completa
                translation_index: Dict[str, Dict] = {}
                for idx, entry in enumerate(self.entries):
                    if entry.translated() and entry.msgid:
                        msgstr = str(entry.msgstr).strip() if entry.msgstr else ""
                        if msgstr:  # Solo incluir si tiene contenido
                            speaker = self.extract_speaker_from_metadata(entry)
                            translation_index[entry.msgid] = {
                                'msgstr': msgstr,
                                'index': idx,
                                'speaker': speaker or ''
                            }
                
                # Copiar traducciones similares
                for i, entry in enumerate(self.entries):
                    if not entry.translated() and entry.msgid:
                        # Buscar msgid similar
                        best_match = None
                        best_ratio = 0.0
                        best_source = None
                        
                        for existing_msgid, source_data in translation_index.items():
                            ratio = SequenceMatcher(None, entry.msgid, existing_msgid).ratio()
                            if ratio > best_ratio and ratio >= 0.8:  # 80% de similitud mínimo
                                best_ratio = ratio
                                best_match = existing_msgid
                                best_source = source_data
                        
                        if best_match:
                            source_msgstr = best_source.get('msgstr', '')
                            if source_msgstr:  # Solo copiar si tiene contenido
                                entry.msgstr = source_msgstr
                                
                                # Guardar información de copia
                                if i not in self.entry_metadata:
                                    self.entry_metadata[i] = {}
                                self.entry_metadata[i]['copied_from'] = {
                                    'index': best_source['index'],
                                    'speaker': best_source['speaker']
                                }
                                
                                # Marcar como "a revisar" solo si la opción está activada
                                if mark_for_review:
                                    self.entry_metadata[i]['needs_review'] = True
                                
                                copied_count += 1
                        
                        # Actualizar progreso cada 10 entradas
                        if copied_count % 10 == 0:
                            self.root.after(0, lambda: self.status_bar.config(
                                text=f"Copiando traducciones... {copied_count} copiadas"))
            
            # Contar cuántas entradas sin traducir tienen un MsgId idéntico ya traducido
            available_count = 0
            msgid_to_translated = {}
            for idx, entry in enumerate(self.entries):
                if entry.translated() and entry.msgid:
                    msgstr = str(entry.msgstr).strip() if entry.msgstr else ""
                    if msgstr:  # Solo contar si tiene contenido
                        msgid_to_translated[entry.msgid] = True
            
            for entry in self.entries:
                if not entry.translated() and entry.msgid and entry.msgid in msgid_to_translated:
                    available_count += 1
            
            self.root.after(0, self.update_entries_list)
            self.root.after(0, lambda: setattr(self, 'has_unsaved_changes', True))
            self.root.after(0, self.update_window_title)
            
            # Actualizar display de entrada actual si está seleccionada
            self.root.after(0, lambda: self._refresh_current_entry_display())
            
            status = f"Copia completada: {copied_count} traducciones copiadas"
            self.root.after(0, lambda text=status: self.status_bar.config(text=text))
            review_text = "y marcadas como 'a revisar'" if mark_for_review else ""
            
            if mode == "to_review":
                message = (
                    f"Se actualizaron {copied_count} entradas marcadas a revisar "
                    "con la traducción de otra entrada que tiene el mismo texto original."
                )
                if not mark_for_review:
                    message += "\nEsas entradas dejan de estar marcadas a revisar."
            else:
                message = f"Se copiaron {copied_count} traducciones."
                if mark_for_review:
                    message += f"\nTodas han sido {review_text}."
                if available_count > 0:
                    message += (
                        f"\n\nDe las entradas sin traducir, {available_count} tienen otra "
                        "entrada con el mismo MsgId que sí está traducida."
                    )
            
            self.root.after(0, lambda text=message: messagebox.showinfo("Completado", text))
        
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error durante la copia:\n{str(e)}"))
        finally:
            self.is_processing = False
    def on_closing(self):
        """Maneja el cierre de la ventana"""
        if self.has_unsaved_changes:
            response = messagebox.askyesnocancel(
                "Cambios sin guardar",
                "Tienes cambios sin guardar. ¿Deseas guardarlos antes de salir?\n\n"
                "Sí: Guardar y salir\n"
                "No: Salir sin guardar\n"
                "Cancelar: Volver al editor"
            )
            if response is True:
                if not self.save_po_file():
                    return  # Usuario canceló el guardado, no cerrar
            elif response is None:
                return  # Usuario canceló, no cerrar
        
        self.root.destroy()


def main():
    root = tk.Tk()
    app = POEditorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
