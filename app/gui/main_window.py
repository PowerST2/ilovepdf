import os
from typing import List

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.pdf_ops import (
    PdfPageRef,
    build_page_list_from_pdfs,
    export_ordered_pages,
    merge_pdfs,
    parse_page_ranges,
    split_pdf_every_page,
    split_pdf_ranges,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("I Love PDF - Desktop")
        self.resize(980, 700)
        self._thumb_cache: dict[tuple[str, int], QIcon] = {}
        self._thumb_size = QSize(140, 200)

        tabs = QTabWidget()
        tabs.addTab(self._build_merge_tab(), "Unir")
        tabs.addTab(self._build_split_tab(), "Separar")
        tabs.addTab(self._build_order_tab(), "Ordenar")

        self.setCentralWidget(tabs)
        self.statusBar().showMessage(
            "Nota: editar PDFs firmados invalida la firma digital."
        )

    # --- Merge tab ---
    def _build_merge_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.merge_list = QListWidget()
        self.merge_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        btn_add = QPushButton("Agregar PDFs")
        btn_remove = QPushButton("Quitar seleccion")
        btn_up = QPushButton("Subir")
        btn_down = QPushButton("Bajar")
        btn_merge = QPushButton("Unir y guardar")

        btn_add.clicked.connect(self._merge_add_pdfs)
        btn_remove.clicked.connect(self._merge_remove_selected)
        btn_up.clicked.connect(lambda: self._move_selected(self.merge_list, -1))
        btn_down.clicked.connect(lambda: self._move_selected(self.merge_list, 1))
        btn_merge.clicked.connect(self._merge_save)

        btn_row = QHBoxLayout()
        for btn in [btn_add, btn_remove, btn_up, btn_down, btn_merge]:
            btn_row.addWidget(btn)

        layout.addWidget(QLabel("Lista de PDFs a unir:"))
        layout.addWidget(self.merge_list)
        layout.addLayout(btn_row)

        return widget

    def _merge_add_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar PDFs", "", "PDF Files (*.pdf)"
        )
        for path in paths:
            self.merge_list.addItem(path)

    def _merge_remove_selected(self) -> None:
        for item in self.merge_list.selectedItems():
            self.merge_list.takeItem(self.merge_list.row(item))

    def _merge_save(self) -> None:
        if self.merge_list.count() == 0:
            self._warn("No hay PDFs para unir.")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF unido", "", "PDF Files (*.pdf)"
        )
        if not output_path:
            return

        paths = [self.merge_list.item(i).text() for i in range(self.merge_list.count())]
        try:
            merge_pdfs(paths, output_path)
        except Exception as exc:
            self._error(str(exc))
            return

        self._info("PDF unido correctamente.")

    # --- Split tab ---
    def _build_split_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        file_row = QHBoxLayout()
        self.split_file_input = QLineEdit()
        btn_browse = QPushButton("Buscar PDF")
        btn_browse.clicked.connect(self._split_browse)
        file_row.addWidget(QLabel("PDF:"))
        file_row.addWidget(self.split_file_input)
        file_row.addWidget(btn_browse)

        mode_box = QGroupBox("Modo")
        mode_layout = QVBoxLayout(mode_box)
        self.split_every_radio = QRadioButton("Cada pagina")
        self.split_range_radio = QRadioButton("Rangos")
        self.split_every_radio.setChecked(True)
        self.split_range_input = QLineEdit()
        self.split_range_input.setPlaceholderText("Ej: 1-3,5,7-9")
        mode_layout.addWidget(self.split_every_radio)
        mode_layout.addWidget(self.split_range_radio)
        mode_layout.addWidget(self.split_range_input)

        out_row = QHBoxLayout()
        self.split_out_dir = QLineEdit()
        btn_out_dir = QPushButton("Carpeta de salida")
        btn_out_dir.clicked.connect(self._split_pick_dir)
        out_row.addWidget(QLabel("Salida:"))
        out_row.addWidget(self.split_out_dir)
        out_row.addWidget(btn_out_dir)

        name_row = QHBoxLayout()
        self.split_base_name = QLineEdit("parte")
        name_row.addWidget(QLabel("Nombre base:"))
        name_row.addWidget(self.split_base_name)

        btn_run = QPushButton("Separar")
        btn_run.clicked.connect(self._split_run)

        layout.addLayout(file_row)
        layout.addWidget(mode_box)
        layout.addLayout(out_row)
        layout.addLayout(name_row)
        layout.addWidget(btn_run)

        return widget

    def _split_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self.split_file_input.setText(path)

    def _split_pick_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if path:
            self.split_out_dir.setText(path)

    def _split_run(self) -> None:
        input_path = self.split_file_input.text().strip()
        output_dir = self.split_out_dir.text().strip()
        base_name = self.split_base_name.text().strip() or "parte"

        if not input_path or not os.path.isfile(input_path):
            self._warn("Selecciona un PDF valido.")
            return
        if not output_dir:
            self._warn("Selecciona una carpeta de salida.")
            return

        try:
            if self.split_every_radio.isChecked():
                split_pdf_every_page(input_path, output_dir, base_name)
            else:
                from pypdf import PdfReader

                reader = PdfReader(input_path)
                max_page = len(reader.pages)
                if max_page == 0:
                    raise ValueError("No se pudo leer el PDF.")

                ranges = parse_page_ranges(self.split_range_input.text(), max_page)
                if not ranges:
                    raise ValueError("Ingresa rangos validos.")
                split_pdf_ranges(input_path, ranges, output_dir, base_name)
        except Exception as exc:
            self._error(str(exc))
            return

        self._info("PDF separado correctamente.")

    # --- Order tab ---
    def _build_order_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.order_list = QListWidget()
        self.order_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.order_list.setIconSize(self._thumb_size)
        self.order_list.setSpacing(6)

        btn_add = QPushButton("Agregar PDFs (append)")
        btn_insert = QPushButton("Insertar PDFs en seleccion")
        btn_remove = QPushButton("Quitar seleccion")
        btn_up = QPushButton("Subir")
        btn_down = QPushButton("Bajar")
        btn_export = QPushButton("Exportar")

        btn_add.clicked.connect(self._order_add_pdfs)
        btn_insert.clicked.connect(self._order_insert_pdfs)
        btn_remove.clicked.connect(self._order_remove_selected)
        btn_up.clicked.connect(lambda: self._move_selected(self.order_list, -1))
        btn_down.clicked.connect(lambda: self._move_selected(self.order_list, 1))
        btn_export.clicked.connect(self._order_export)

        btn_row = QHBoxLayout()
        for btn in [btn_add, btn_insert, btn_remove, btn_up, btn_down, btn_export]:
            btn_row.addWidget(btn)

        layout.addWidget(QLabel("Lista de paginas (reordenar/remover):"))
        layout.addWidget(self.order_list)
        layout.addLayout(btn_row)

        return widget

    def _order_add_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar PDFs", "", "PDF Files (*.pdf)"
        )
        if not paths:
            return

        try:
            pages = build_page_list_from_pdfs(paths)
        except Exception as exc:
            self._error(str(exc))
            return

        self._append_pages_to_list(self.order_list, pages)

    def _order_insert_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar PDFs", "", "PDF Files (*.pdf)"
        )
        if not paths:
            return

        try:
            pages = build_page_list_from_pdfs(paths)
        except Exception as exc:
            self._error(str(exc))
            return

        insert_at = self.order_list.currentRow()
        if insert_at < 0:
            self._append_pages_to_list(self.order_list, pages)
            return

        for offset, page_ref in enumerate(pages):
            item = self._page_item(page_ref)
            self.order_list.insertItem(insert_at + offset, item)

    def _order_remove_selected(self) -> None:
        for item in self.order_list.selectedItems():
            self.order_list.takeItem(self.order_list.row(item))

    def _order_export(self) -> None:
        if self.order_list.count() == 0:
            self._warn("No hay paginas para exportar.")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF ordenado", "", "PDF Files (*.pdf)"
        )
        if not output_path:
            return

        pages: List[PdfPageRef] = []
        for i in range(self.order_list.count()):
            item = self.order_list.item(i)
            page_ref = item.data(Qt.UserRole)
            pages.append(page_ref)

        try:
            export_ordered_pages(pages, output_path)
        except Exception as exc:
            self._error(str(exc))
            return

        self._info("PDF exportado correctamente.")

    # --- Helpers ---
    def _append_pages_to_list(self, list_widget: QListWidget, pages: List[PdfPageRef]) -> None:
        for page_ref in pages:
            list_widget.addItem(self._page_item(page_ref))

    def _page_item(self, page_ref: PdfPageRef) -> QListWidgetItem:
        filename = os.path.basename(page_ref.path)
        label = f"{filename} - p {page_ref.index + 1}"
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, page_ref)
        icon = self._get_page_icon(page_ref)
        if not icon.isNull():
            item.setIcon(icon)
        return item

    def _get_page_icon(self, page_ref: PdfPageRef) -> QIcon:
        key = (page_ref.path, page_ref.index)
        if key in self._thumb_cache:
            return self._thumb_cache[key]

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(page_ref.path)
            page = doc.load_page(page_ref.index)
            rect = page.rect
            if rect.width <= 0 or rect.height <= 0:
                doc.close()
                return QIcon()

            scale = min(
                self._thumb_size.width() / rect.width,
                self._thumb_size.height() / rect.height,
            )
            scale = max(scale, 0.1)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            doc.close()

            image = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format_RGB888,
            )
            icon = QIcon(QPixmap.fromImage(image))
        except Exception:
            return QIcon()

        self._thumb_cache[key] = icon
        return icon

    def _move_selected(self, list_widget: QListWidget, direction: int) -> None:
        selected = list_widget.selectedItems()
        if not selected:
            return

        rows = sorted((list_widget.row(i) for i in selected), reverse=direction > 0)
        for row in rows:
            new_row = row + direction
            if new_row < 0 or new_row >= list_widget.count():
                continue
            item = list_widget.takeItem(row)
            list_widget.insertItem(new_row, item)
            item.setSelected(True)

    def _warn(self, message: str) -> None:
        QMessageBox.warning(self, "Aviso", message)

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, "Error", message)

    def _info(self, message: str) -> None:
        QMessageBox.information(self, "Listo", message)
