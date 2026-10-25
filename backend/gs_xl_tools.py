"""
Some helper functions for genscan to work with MS Excel files
"""

import logging
import os

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    NamedStyle,
    PatternFill,
    Side,
    numbers,
)
from openpyxl.utils import absolute_coordinate, get_column_letter, quote_sheetname
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.worksheet import Worksheet

from gs_file_tools import check_file_exists
from gs_xl_headers import headers

############################
# Standard XL index
############################

logger = logging.getLogger("gsw_logger")


def create_index_file(filepath=None):
    """
    Create an new index XL workbook

    Parameters
        filepath (string): file path of the workbook

    Return:
        wb (openpyxl object): Object of created workbook
    """

    if filepath is None:
        logger.debug("No file path provided")
        return None

    # Exception errors
    #   PermissionError: Permission denied (file open)

    # Create workbook
    wb = Workbook()
    ws = wb.active

    # Add some special styles
    # Create a custom date style
    date_style = NamedStyle(name="custom_date_style", number_format="dd-mm-yyyy")

    # Add the custom date style to the workbook's styles
    if "custom_date_style" not in wb.named_styles:
        wb.add_named_style(date_style)

    # Add sheets and content
    # _, sheet_title = os.path.split(os.path.split(filepath)[0])
    add_xl_sheet(ws, "RBP")
    add_statistiek_sheet(wb)

    # Save the workbook
    wb.save(filepath)

    logger.debug("Index Excel workbook created")

    return wb


def add_xl_sheet(xl_object=None, sheet_title=None):
    """
    Create the XL sheet.
    When passing a Workbook, it is added at the end of worksheets
    When passing a Worksheet, it is created in that worksheet

    Parameter:
        xl_object (openpyxl): a Openpyxl Workbook or Worksheet
    """

    if xl_object is None or sheet_title is None:
        logger.debug("Nothing passed to function. Returning")

        return

    if isinstance(xl_object, Workbook):
        # Create new sheet in workbook
        logger.debug("Adding worksheet to workbook")
        ws = xl_object.create_sheet()
    elif isinstance(xl_object, Worksheet):
        # Set up in passed worksheet
        logger.debug("Setting up existing worksheet")
        ws = xl_object
    else:
        logger.debug("No XL object passed to function. Returning")

        return

    ws.title = sheet_title
    ws.sheet_properties.tabColor = "0070C0"

    # Borders
    thin = Side(border_style="thin", color="000000")
    medium = Side(border_style="medium", color="000000")
    # thick = Side(border_style="thick", color="000000")

    # Title part 1
    ws["A1"] = "Rouwbrievenproject"
    ws["A1"].font = Font(name="Calibri", size=52, bold=True, color="FFFF00")
    ws["A1"].fill = PatternFill("solid", fgColor="0070C0")
    ws["A1"].border = Border(left=medium, top=medium, bottom=medium)
    ws.merge_cells("A1:D1")

    # Title part 2
    ws["E1"] = sheet_title
    ws["E1"].font = Font(name="Calibri", size=52, bold=True, color="4472C4")
    ws["E1"].fill = PatternFill("solid", fgColor="FFFF00")
    ws["E1"].border = Border(right=medium, top=medium, bottom=medium)

    # Set row index where headers need to come
    header_row = 3
    ws.row_dimensions[header_row].height = 21

    # Header properties are read from gs_xl_headers.py
    for index, header_properties in enumerate(headers):
        # Set starting column for headers
        column_index = index + 1
        column_letter = get_column_letter(column_index)

        # General header style
        ws.cell(row=header_row, column=column_index).border = Border(
            left=thin, right=thin, top=medium, bottom=medium
        )
        ws.cell(row=header_row, column=column_index).font = Font(
            name="Calibri", size=11, bold=True
        )
        ws.cell(row=header_row, column=column_index).alignment = Alignment(
            vertical="center"
        )

        # Add headers with styles
        for header_property, value in header_properties.items():
            match header_property:
                case "header":
                    ws.cell(row=header_row, column=column_index).value = value
                case "note":
                    comment = Comment(text=value, author="", width=200)
                    ws.cell(row=header_row, column=column_index).comment = comment
                case "color":
                    ws.cell(row=header_row, column=column_index).fill = PatternFill(
                        "solid", fgColor=value
                    )
                case "font_color":
                    ws.cell(row=header_row, column=column_index).font = Font(
                        color=value, name="Calibri", size=11, bold=True
                    )
                case "width":
                    ws.column_dimensions[column_letter].width = value
                case "hidden":
                    ws.column_dimensions[column_letter].hidden = value

    last_column_letter = get_column_letter(xl_object.max_column)
    last_row = xl_object.max_row

    # Merge title part 2
    ws.merge_cells(f"E1:{last_column_letter}1")

    # Freeze panes
    ws.freeze_panes = f"E{header_row+1}"

    # Mark first header
    ref = f"{quote_sheetname(ws.title)}!{absolute_coordinate(f'A{header_row}')}"
    defined_name = DefinedName("first_header", attr_text=ref)
    ws.defined_names.add(defined_name)

    # Set filter
    ws.auto_filter.ref = f"A{header_row}:{last_column_letter}{last_row}"

    logger.debug("Sheet created")


def add_statistiek_sheet(xl_object=None):
    """
    Create the Statistiek sheet.
    When passing a Workbook, it is added at the end of worksheets
    When passing a Worksheet, it is created in that worksheet

    Parameter:
        xl_object (openpyxl): a Openpyxl Workbook or Worksheet
    """

    if xl_object is None:
        logger.debug("Nothing passed to function. Returning")

        return

    if isinstance(xl_object, Workbook):
        # Create new sheet in workbook
        logger.debug("Adding worksheet to workbook")
        ws = xl_object.create_sheet()
    elif isinstance(xl_object, Worksheet):
        # Set up in passed worksheet
        logger.debug("Setting up existing worksheet")
        ws = xl_object
    else:
        logger.debug("Nothing no XL object passed to function. Returning")

        return

    center_aligned_text = Alignment(horizontal="center")
    right_aligned_text = Alignment(horizontal="right")
    big_font = Font(name="Calibri", size=26)
    bold_font = Font(bold=True)
    numbers_format_percent = numbers.FORMAT_PERCENTAGE_00

    ws.title = "Statistiek"
    ws.sheet_properties.tabColor = "FFFF00"

    # Sheet data. First row and first column are just helpers.
    cell_formulas = [
        ["A", "B", "C", "D"],
        [1, "Statistiek"],
        [2, "", "Aantal", "Percentage"],
        [3, "Onbekend geslacht", "=C16-C7", "=C3/C7"],
        [4, "Mannen (M)", '=COUNTIF(RBP!E:E,"M")', "=C4/C7"],
        [5, "Vrouwen (V)", '=COUNTIF(RBP!E:E,"V")', "=C5/C7"],
        [6, "Geslachtloos (X)", '=COUNTIF(RBP!E:E,"X")', "=C6/C7"],
        [7, "Totaal", "=SUM(C4:C6)"],
        [8],
        [9, "Met foto", '=COUNTIF(RBP!F:F,"X")', "=C9/C16"],
        [10],
        [11, "Rouwbrieven (RB)", '=COUNTIF(RBP!A:A,"RB")', "=C11/C16"],
        [12, "Overlijdensberichten (OB)", '=COUNTIF(RBP!A:A,"OB")', "=C12/C16"],
        [13, "Bidprentjes (BP)", '=COUNTIF(RBP!A:A,"BP")', "=C13/C16"],
        [14, "Krantenberichten (KB)", '=COUNTIF(RBP!A:A,"KB")', "=C14/C16"],
        [
            15,
            "Krantenoverlijdensberichten (KO)",
            '=COUNTIF(RBP!A:A,"KO")',
            "=C15/C16",
        ],
        [16, "Totaal", "=SUM(C11:C15)"],
    ]

    # Build the sheet
    for row in cell_formulas:
        ws.append(row)

    # Add some formatting
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 8
    ws.column_dimensions["D"].width = 12

    ws["B2"].font = bold_font
    ws["B8"].font = bold_font
    ws["B17"].font = bold_font
    ws["B2"].font = big_font

    for row in range(1, 18):
        ws[f"A{row}"] = ""
        cell = ws[f"B{row}"]
        cell.alignment = right_aligned_text
        cell = ws[f"C{row}"]
        cell.alignment = center_aligned_text
        cell = ws[f"D{row}"]
        cell.alignment = center_aligned_text
        cell.number_format = numbers_format_percent

    ws["C3"].alignment = center_aligned_text
    ws["D3"].alignment = center_aligned_text

    # Remove row 1, it was just a helper
    ws.delete_rows(1)

    logger.debug("Sheet created")


def open_index_file(filepath=None):
    """
    Open an existing index XL workbook or create one

    Parameters
        filepath (string): file path of the workbook

    Return:
        wb (openpyxl object): Object to opened workbook
    """

    if filepath is None:
        logger.debug("No file path provided")

        return None

    if check_file_exists(filepath):
        logger.debug("Index file exists. Accessing file")
        wb = load_workbook(filename=filepath)
    else:
        logger.debug("Index file does not exists. Creating file")
        wb = create_index_file(filepath)

    return wb


def add_row_to_table(filepath=None, new_row=None):
    """
    Add a row to the RBP sheet.

    Parameter:
        xl_object (openpyxl): a Openpyxl Workbook or Worksheet
        new_row (list): Data to add to row (order and number of elements is important!)

    Return:
        True, False or None
    """

    if filepath is None or new_row is None:
        logger.debug("Wrong parameters passed to function. Returning")
        return None

    # Open the workbook, sheet and access the table
    wb = open_index_file(filepath)
    if wb is None:
        logger.debug("No workbook available. Skipping")
        return None

    # Append the new row to the worksheet
    ws = wb["RBP"]
    ws.append(new_row)
    logger.debug("Row of data added to index file")

    # Save the workbook with changes
    wb.save(filepath)
    logger.debug("Saved index file")

    return True


def add_row_to_index(obituary):
    """
    Add a row of obituary data to the index file

    Parameters:
      obituary (Obituary object): initial obituary information

    """

    # Save index here:
    index_filename = f"_Index_{os.path.split(obituary.folder_name)[1]}.xlsx"
    file_path = os.path.normpath(os.path.join(obituary.folder_name, index_filename))
    logger.debug("%15s:%s", "Index file", file_path)

    # Create birth date
    birth_date = (
        f"0{obituary.birth_day if isinstance(obituary.birth_day, int) else 00}-"[-3:]
    )
    birth_date += (
        f"0{obituary.birth_month if isinstance(obituary.birth_month, int) else 00}-"[
            -3:
        ]
    )
    birth_date += (
        f"{obituary.birth_year if isinstance(obituary.birth_year, int) else '0000'}"
    )

    # Create death date
    death_date = (
        f"0{obituary.death_day if isinstance(obituary.death_day, int) else 00}-"[-3:]
    )
    death_date += (
        f"0{obituary.death_month if isinstance(obituary.death_month, int) else 00}-"[
            -3:
        ]
    )
    death_date += (
        f"{obituary.death_year if isinstance(obituary.death_year, int) else '0000'}"
    )

    # Build row data
    data = [
        obituary.obituary_type.upper(),
        obituary.new_file_name,
        obituary.first_name,
        obituary.last_name,
        obituary.gender.upper(),
        "X" if obituary.face else "",
        birth_date,
        obituary.birth_place,
        death_date,
        obituary.death_place,
        obituary.note,
    ]
    logger.debug("Index data created")

    # Add row to index file
    add_row_to_table(filepath=file_path, new_row=data)
