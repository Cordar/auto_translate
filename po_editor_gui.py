#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Editor GUI para archivos .po
Permite editar traducciones, pretraducir con DeepL/Google, y copiar traducciones existentes.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import polib
from pathlib import Path
from deep_translator import DeeplTranslator, GoogleTranslator
import threading
from typing import Dict, Optional
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
            "Inglés": "en-GB",
            "Catalán": "ca",
            "Francés": "fr",
            "Alemán": "de",
            "Italiano": "it",
            "Portugués": "pt"
        }
        
        self.source_lang = "es"
        self.target_lang = "en-GB"
        
        # Mapeo de idiomas a códigos de LanguageTool
        self.language_tool_codes = {
            "es": "es",
            "en-GB": "en-GB",
            "ca": "ca",
            "fr": "fr",
            "de": "de-DE",
            "it": "it",
            "pt": "pt-PT"
        }
        
        # Inicializar LanguageTool si está disponible
        self.language_tool = None
        if LANGUAGE_TOOL_AVAILABLE:
            try:
                self.language_tool = language_tool_python.LanguageTool('ca')  # Por defecto catalán
            except Exception as e:
                print(f"Error inicializando LanguageTool: {e}")
                self.language_tool = None
        
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
        
        # Contadores de estadísticas
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
        
        # ========== PANEL DERECHO: Editor de entrada ==========
        right_top = ttk.Frame(right_frame)
        right_top.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(right_top, text="Editor de Entrada", font=("Arial", 12, "bold")).pack()
        
        # Acciones globales
        actions_frame = ttk.LabelFrame(right_frame, text="Acciones Globales", padding="10")
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
        
        # Botones de acciones
        ttk.Button(actions_frame, text="Pretraducir (DeepL/Google)", 
                   command=self.pretranslate_all).pack(fill=tk.X, pady=2)
        
        copy_frame = ttk.Frame(actions_frame)
        copy_frame.pack(fill=tk.X, pady=5)
        
        self.copy_mode_var = tk.StringVar(value="identical")
        ttk.Radiobutton(copy_frame, text="Idénticas", variable=self.copy_mode_var, 
                       value="identical").pack(side=tk.LEFT, padx=5, pady=3)
        ttk.Radiobutton(copy_frame, text="Similares", variable=self.copy_mode_var, 
                       value="similar").pack(side=tk.LEFT, padx=5, pady=3)
        
        self.copy_mark_review_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(copy_frame, text="Marcar como 'a revisar'", 
                       variable=self.copy_mark_review_var).pack(side=tk.LEFT, padx=5, pady=3)
        
        ttk.Button(copy_frame, text="Copiar Traducciones", 
                  command=self.copy_translations).pack(side=tk.LEFT, padx=5, pady=5, ipady=3)
        
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
        
        # Label para mostrar "copiada de" y Speaker
        self.copied_from_label = ttk.Label(msgstr_frame, text="", foreground="blue", font=("Arial", 9, "italic"))
        self.copied_from_label.pack(fill=tk.X, padx=5, pady=2)
        
        self.msgstr_text = scrolledtext.ScrolledText(msgstr_frame, height=8, wrap=tk.WORD)
        self.msgstr_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.msgstr_text.bind("<KeyRelease>", self.on_translation_changed)
        
        # Botones de acción para entrada actual
        entry_actions = ttk.Frame(right_frame)
        entry_actions.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(entry_actions, text="Traducir (DeepL/Google)", 
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
            text="✓ Okay", 
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
        
        # Configuración de API key de DeepL
        config_frame = ttk.Frame(right_frame)
        config_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(config_frame, text="DeepL API Key (opcional):").pack(side=tk.LEFT, padx=5)
        self.deepl_key_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.deepl_key_var, width=40, show="*").pack(side=tk.LEFT, padx=5)
        
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
        self.target_lang = self.languages.get(lang_name, "en-GB")
    
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
                speaker = match.group(1)
            else:
                # Buscar "Context": "SPEAKER ->"
                match = re.search(r'"Context"\s*:\s*"([^"]+)\s*->"', entry.comment)
                if match:
                    speaker = match.group(1)
        
        # Buscar en tcomment si no se encontró
        if not speaker and entry.tcomment:
            match = re.search(r'"Speaker"\s*:\s*"([^"]+)"', entry.tcomment)
            if match:
                speaker = match.group(1)
            else:
                match = re.search(r'"Context"\s*:\s*"([^"]+)\s*->"', entry.tcomment)
                if match:
                    speaker = match.group(1)
        
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
                        except json.JSONDecodeError:
                            # Ignorar JSON inválido silenciosamente
                            pass
        
        # Ahora mapear la metadata a los índices actuales después de ordenar
        self.entry_metadata = {}
        for i, entry in enumerate(self.entries):
            if entry.msgid in temp_metadata_by_msgid:
                self.entry_metadata[i] = temp_metadata_by_msgid[entry.msgid]
    
    def save_metadata_to_po(self):
        """Guarda metadata personalizada en los comentarios del archivo .po"""
        # Primero, limpiar todas las líneas POEDITOR_METADATA de todas las entradas
        for entry in self.entries:
            if entry.tcomment:
                lines = entry.tcomment.split('\n')
                lines = [line for line in lines if not line.strip().startswith('POEDITOR_METADATA:')]
                entry.tcomment = '\n'.join(lines).strip()
        
        # Luego, agregar metadata solo para las entradas que la tienen
        for i, entry in enumerate(self.entries):
            if i in self.entry_metadata:
                metadata = self.entry_metadata[i]
                # Guardar si tiene needs_review o copied_from
                if metadata.get('needs_review') or metadata.get('copied_from'):
                    # Serializar metadata a JSON compacto
                    json_str = json.dumps(metadata, ensure_ascii=False, separators=(',', ':'))
                    
                    # Agregar nueva metadata
                    metadata_line = f"POEDITOR_METADATA:{json_str}"
                    if entry.tcomment:
                        entry.tcomment = f"{entry.tcomment}\n{metadata_line}"
                    else:
                        entry.tcomment = metadata_line
    
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
        # Limpiar lista
        for item in self.entries_tree.get_children():
            self.entries_tree.delete(item)
        
        # Filtrar entradas
        filter_text = self.filter_var.get().lower()
        show_only_untranslated = self.show_translated_var.get()
        show_only_review = self.show_review_var.get()
        
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
            
            # Marcar visualmente las que necesitan revisión
            if needs_review:
                self.entries_tree.set(item_id, "Estado", status)
        
        # Actualizar estadísticas
        self.update_statistics()
    
    def on_entry_select(self, event):
        """Se ejecuta cuando se selecciona una entrada de la lista"""
        selection = self.entries_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.entries_tree.item(item)['values']
        if not values:
            return
        
        index = int(values[0]) - 1
        if 0 <= index < len(self.entries):
            self.display_entry(self.entries[index])
            self.current_entry_index = index
    
    def display_entry(self, entry):
        """Muestra una entrada en el editor"""
        # MsgID
        self.msgid_text.config(state=tk.NORMAL)
        self.msgid_text.delete(1.0, tk.END)
        msgid_display = entry.msgid
        if entry.msgid_plural:
            msgid_display += f"\n\nPlural:\n{entry.msgid_plural}"
        self.msgid_text.insert(1.0, msgid_display)
        self.msgid_text.config(state=tk.DISABLED)
        
        # MsgStr
        self.msgstr_text.delete(1.0, tk.END)
        if entry.msgid_plural:
            # Mostrar plurales en formato [0]: texto\n[1]: texto
            plural_lines = []
            for idx in sorted(entry.msgstr_plural.keys()):
                plural_lines.append(f"[{idx}]: {entry.msgstr_plural[idx]}")
            self.msgstr_text.insert(1.0, "\n".join(plural_lines))
        else:
            self.msgstr_text.insert(1.0, entry.msgstr)
        
        # Estado de "a revisar"
        needs_review = self.entry_metadata.get(self.current_entry_index, {}).get('needs_review', False)
        self.needs_review_var.set(needs_review)
        
        # Mostrar información de "copiada de" y Speaker
        entry_meta = self.entry_metadata.get(self.current_entry_index, {})
        copied_from = entry_meta.get('copied_from')
        speaker = self.extract_speaker_from_metadata(entry)
        
        copied_from_text = ""
        if copied_from:
            source_speaker = copied_from.get('speaker', '')
            source_index = copied_from.get('index', '')
            if source_speaker:
                copied_from_text = f"📋 Copiada de entrada #{source_index + 1} (Speaker: {source_speaker})"
            else:
                copied_from_text = f"📋 Copiada de entrada #{source_index + 1}"
        
        if speaker:
            if copied_from_text:
                copied_from_text += f" | 🎭 Speaker actual: {speaker}"
            else:
                copied_from_text = f"🎭 Speaker: {speaker}"
        
        self.copied_from_label.config(text=copied_from_text)
        
        # Mostrar/ocultar botones de navegación según el estado
        is_translated = entry.translated()
        
        # Ocultar todos primero
        self.next_untranslated_btn.pack_forget()
        self.next_review_btn.pack_forget()
        self.okay_btn.pack_forget()
        
        if needs_review:
            # Si está marcada como "a revisar", mostrar botón "Siguiente a revisar" y "Okay"
            self.next_review_btn.pack(side=tk.LEFT, padx=5)
            self.okay_btn.pack(side=tk.LEFT, padx=5)
        elif not is_translated:
            # Si no está traducida, mostrar "Siguiente sin traducir"
            self.next_untranslated_btn.pack(side=tk.LEFT, padx=5)
        # Si está traducida y no necesita revisión, no mostrar ningún botón de navegación
        
        # Si no hay entrada seleccionada, ocultar todos los botones de navegación
        if self.current_entry_index is None:
            self.next_untranslated_btn.pack_forget()
            self.next_review_btn.pack_forget()
            self.okay_btn.pack_forget()
        
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
    
    def on_translation_changed(self, event):
        """Se ejecuta cuando se modifica la traducción"""
        if self.current_entry_index is None:
            return
        
        entry = self.entries[self.current_entry_index]
        new_translation = self.msgstr_text.get(1.0, tk.END).strip()
        
        if entry.msgid_plural:
            # Manejar plurales (formato: [0]: texto\n[1]: texto)
            lines = new_translation.split('\n')
            entry.msgstr_plural.clear()
            for line in lines:
                if ':' in line:
                    idx_str, text = line.split(':', 1)
                    try:
                        idx = int(idx_str.strip().strip('[]'))
                        entry.msgstr_plural[idx] = text.strip()
                    except ValueError:
                        pass
        else:
            entry.msgstr = new_translation
        
        # Marcar como cambios sin guardar
        self.has_unsaved_changes = True
        self.update_window_title()
        
        # Actualizar lista
        self.update_entries_list()
    
    def translate_current(self):
        """Traduce la entrada actual usando DeepL o Google"""
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
                # Intentar DeepL primero
                deepl_key = self.deepl_key_var.get().strip()
                translator = None
                
                if deepl_key:
                    try:
                        translator = DeeplTranslator(api_key=deepl_key, source=self.source_lang, target=self.target_lang)
                    except:
                        pass
                
                if not translator:
                    try:
                        translator = DeeplTranslator(source=self.source_lang, target=self.target_lang, use_free_api=True)
                    except:
                        pass
                
                if not translator:
                    translator = GoogleTranslator(source=self.source_lang, target=self.target_lang)
                
                translated = translator.translate(text_to_translate)
                
                # Actualizar en el hilo principal
                self.root.after(0, lambda: self.msgstr_text.delete(1.0, tk.END))
                self.root.after(0, lambda: self.msgstr_text.insert(1.0, translated))
                self.root.after(0, self.on_translation_changed)
                self.root.after(0, lambda: self.status_bar.config(text="Traducción completada"))
                # on_translation_changed ya marca como cambios sin guardar
            except Exception as e:
                messagebox.showerror("Error", f"Error al traducir:\n{str(e)}")
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
        
        if self.current_entry_index is None:
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
                    self.root.after(0, lambda: self.msgstr_text.delete(1.0, tk.END))
                    self.root.after(0, lambda: self.msgstr_text.insert(1.0, corrected_text))
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
    
    def clear_current_translation(self):
        """Limpia la traducción actual"""
        self.msgstr_text.delete(1.0, tk.END)
        self.on_translation_changed(None)
    
    def toggle_needs_review(self):
        """Marca o desmarca la entrada actual como 'a revisar'"""
        if self.current_entry_index is None:
            return
        
        needs_review = self.needs_review_var.get()
        
        if self.current_entry_index not in self.entry_metadata:
            self.entry_metadata[self.current_entry_index] = {}
        
        self.entry_metadata[self.current_entry_index]['needs_review'] = needs_review
        
        # Si se desmarca (okay), limpiar metadata de copiada_from
        if not needs_review:
            if 'copied_from' in self.entry_metadata[self.current_entry_index]:
                del self.entry_metadata[self.current_entry_index]['copied_from']
            
            # Si no hay más metadata útil, eliminar la entrada completamente
            if self.current_entry_index in self.entry_metadata:
                if not self.entry_metadata[self.current_entry_index].get('copied_from'):
                    del self.entry_metadata[self.current_entry_index]
            
            # Actualizar display para ocultar el label
            self.display_entry(self.entries[self.current_entry_index])
        
        # Actualizar lista
        self.update_entries_list()
        self.has_unsaved_changes = True
        self.update_window_title()
    
    def mark_as_okay(self):
        """Marca la entrada actual como 'okay' (desmarca 'a revisar') y salta a la siguiente"""
        if self.current_entry_index is None:
            return
        
        # Guardar el índice actual antes de desmarcar
        current_idx = self.current_entry_index
        
        # Desmarcar "a revisar" y limpiar metadata
        self.needs_review_var.set(False)
        self.toggle_needs_review()
        
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
            f"¿Pretraducir todas las entradas sin traducir?\n\n"
            f"Esto puede tardar varios minutos dependiendo del número de entradas."
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
            # Inicializar traductor
            deepl_key = self.deepl_key_var.get().strip()
            translator = None
            
            if deepl_key:
                try:
                    translator = DeeplTranslator(api_key=deepl_key, source=self.source_lang, target=self.target_lang)
                except:
                    pass
            
            if not translator:
                try:
                    translator = DeeplTranslator(source=self.source_lang, target=self.target_lang, use_free_api=True)
                except:
                    pass
            
            if not translator:
                translator = GoogleTranslator(source=self.source_lang, target=self.target_lang)
            
            translated_count = 0
            error_count = 0
            
            for i, entry in enumerate(self.entries):
                if not entry.translated() and entry.msgid:
                    try:
                        translated = translator.translate(entry.msgid)
                        entry.msgstr = translated
                        
                        # Marcar como "a revisar"
                        if i not in self.entry_metadata:
                            self.entry_metadata[i] = {}
                        self.entry_metadata[i]['needs_review'] = True
                        
                        translated_count += 1
                        
                        # Actualizar progreso cada 10 entradas
                        if translated_count % 10 == 0:
                            self.root.after(0, lambda: self.status_bar.config(
                                text=f"Pretraduciendo... {translated_count} traducidas"))
                    except Exception as e:
                        error_count += 1
                        print(f"Error traduciendo entrada {i}: {str(e)}")
            
            self.root.after(0, self.update_entries_list)
            self.root.after(0, lambda: setattr(self, 'has_unsaved_changes', True))
            self.root.after(0, self.update_window_title)
            self.root.after(0, lambda: self.status_bar.config(
                text=f"Pretraducción completada: {translated_count} traducidas, {error_count} errores"))
            self.root.after(0, lambda: messagebox.showinfo(
                "Completado",
                f"Pretraducción completada.\n{translated_count} entradas traducidas.\n{error_count} errores."))
        
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error durante la pretraducción:\n{str(e)}"))
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
            
            # Crear índice de traducciones existentes con información completa
            # {msgid: {'msgstr': str, 'index': int, 'speaker': str}}
            translation_index: Dict[str, Dict] = {}
            for idx, entry in enumerate(self.entries):
                if entry.translated() and entry.msgid:
                    speaker = self.extract_speaker_from_metadata(entry)
                    translation_index[entry.msgid] = {
                        'msgstr': entry.msgstr,
                        'index': idx,
                        'speaker': speaker or ''
                    }
            
            # Copiar traducciones
            for i, entry in enumerate(self.entries):
                if not entry.translated() and entry.msgid:
                    if mode == "identical":
                        # Buscar msgid idéntico
                        if entry.msgid in translation_index:
                            source = translation_index[entry.msgid]
                            entry.msgstr = source['msgstr']
                            
                            # Guardar información de copia
                            if i not in self.entry_metadata:
                                self.entry_metadata[i] = {}
                            self.entry_metadata[i]['copied_from'] = {
                                'index': source['index'],
                                'speaker': source['speaker']
                            }
                            
                            # Marcar como "a revisar" solo si la opción está activada
                            if mark_for_review:
                                self.entry_metadata[i]['needs_review'] = True
                            
                            copied_count += 1
                    else:  # similar
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
                            entry.msgstr = best_source['msgstr']
                            
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
            
            self.root.after(0, self.update_entries_list)
            self.root.after(0, lambda: setattr(self, 'has_unsaved_changes', True))
            self.root.after(0, self.update_window_title)
            self.root.after(0, lambda: self.status_bar.config(
                text=f"Copia completada: {copied_count} traducciones copiadas"))
            review_text = "y marcadas como 'a revisar'" if mark_for_review else ""
            self.root.after(0, lambda: messagebox.showinfo(
                "Completado",
                f"Se copiaron {copied_count} traducciones." + (f"\nTodas han sido {review_text}." if mark_for_review else "")))
        
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
