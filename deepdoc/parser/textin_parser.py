#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import logging
import os
import re
from io import BytesIO
from timeit import default_timer as timer

import numpy as np
import pdfplumber
import requests
from PIL import Image

from deepdoc.parser.pdf_parser import RAGFlowPdfParser


class TextInParser(RAGFlowPdfParser):
    """
    TextIn-based PDF parser that inherits from RAGFlowPdfParser.

    This parser replaces the OCR and layout recognition steps with TextIn API,
    while maintaining compatibility with RAGFlow's document processing pipeline.
    """

    def __init__(self, api_url=None, app_id=None, secret_code=None):
        """Initialize TextIn parser with API credentials."""
        # Basic attributes needed from parent class
        self.page_from = 0
        self.column_num = 1
        self.parallel_limiter = None
        self.mean_height = []
        self.mean_width = []

        self.app_id = app_id or os.getenv("TEXTIN_APP_ID")
        self.secret_code = secret_code or os.getenv("TEXTIN_SECRET_CODE")
        self.api_url = api_url or "https://api.textin.com/ai/service/v1/pdf_to_markdown"

        if not self.app_id or not self.secret_code:
            raise ValueError("TextIn credentials not provided. Set TEXTIN_APP_ID and TEXTIN_SECRET_CODE.")

    def __call__(self, fnm, need_image=True, zoomin=3, return_html=False,
                 from_page=0, to_page=100000, callback=None, **kwargs):
        """
        Parse PDF using TextIn API.

        Returns:
            tuple: (sections, tables) in RAGFlow format
        """
        start = timer()

        self.boxes = []
        self.page_images = []

        try:
            self.__images__(fnm, zoomin, from_page, to_page, callback)
        except Exception as e:
            logging.warning(f"[TextIn] Failed to load PDF images: {e}")

        if callback:
            callback(0.1, "[TextIn] Calling API...")

        sections, tables, image_items = self._call_textin_api(fnm, from_page, to_page, callback)
        self._convert_to_boxes(sections, from_page, zoomin)

        if callback:
            callback(0.8, f"[TextIn] Converted {len(self.boxes)} text blocks")

        tbls = self._process_tables(tables, need_image, zoomin, return_html)
        tbls.extend(self._process_images(image_items, need_image, zoomin))
        self._simple_text_merge()

        logging.info(f"[TextIn] Parse complete: {len(self.boxes)} boxes, {len(tbls)} tables/images ({timer() - start:.2f}s)")

        if callback:
            callback(1.0, "[TextIn] Done")

        return [(b["text"], self._line_tag(b, zoomin)) for b in self.boxes], tbls

    def parse_pdf(self, filepath=None, binary=None, callback=None,
                  from_page=0, to_page=100000, **kwargs):
        """Unified entry point matching the interface expected by by_textin()."""
        fnm = binary if binary is not None else filepath
        return self(fnm, callback=callback, from_page=from_page, to_page=to_page, **kwargs)

    def __images__(self, fnm, zoomin=3, page_from=0, page_to=10000, callback=None):
        """Load PDF page images for visualization and cropping."""
        try:
            if isinstance(fnm, (str, bytes)):
                pdf_file = fnm if isinstance(fnm, str) else BytesIO(fnm)
            else:
                pdf_file = fnm

            with pdfplumber.open(pdf_file) as pdf:
                self.pdf = pdf
                self.page_images = []
                actual_page_to = min(page_to, len(pdf.pages))
                for page in pdf.pages[page_from:actual_page_to]:
                    img = page.to_image(resolution=72 * zoomin).original
                    self.page_images.append(img)
                self.total_page = len(pdf.pages)

            self.page_chars = [[] for _ in range(len(self.page_images))]
            self.page_cum_height = [0]

        except Exception as e:
            logging.warning(f"[TextIn] Failed to load PDF images: {e}")
            self.page_images = []
            self.page_chars = []
            self.total_page = 0

    def _call_textin_api(self, fnm, from_page, to_page, callback):
        """Call TextIn API to parse PDF."""
        # Prepare binary data
        if isinstance(fnm, str):
            with open(fnm, 'rb') as f:
                data = f.read()
        elif isinstance(fnm, bytes):
            data = fnm
        else:
            data = fnm.getvalue() if hasattr(fnm, 'getvalue') else fnm.read()

        headers = {
            'x-ti-app-id': self.app_id,
            'x-ti-secret-code': self.secret_code,
            'Content-Type': 'application/octet-stream'
        }

        params = {
            'paratext_mode': 'none',
            'formula_level': 2,
            'page_start': from_page + 1,
            'page_count': min(to_page - from_page, 100000),
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                data=data,
                params=params,
                timeout=6000
            )
            response.raise_for_status()
        except Exception as e:
            msg = f"[TextIn] Request failed: {e}"
            if callback:
                callback(0.6, msg)
            raise RuntimeError(msg)

        try:
            result = response.json()
        except ValueError:
            msg = f"[TextIn] Invalid JSON response: {response.text[:200]}"
            if callback:
                callback(0.6, msg)
            raise RuntimeError(msg)

        if result.get('code') != 200:
            error_msg = result.get('message', 'Unknown error')
            msg = f"[TextIn] API error {result.get('code')}: {error_msg}"
            if callback:
                callback(0.6, msg)
            raise RuntimeError(msg)

        if callback:
            callback(0.6, "[TextIn] Processing API response...")

        # Parse response
        sections = []
        tables = []
        image_items = []
        detail = result.get('result', {}).get('detail', [])

        # Collect all items with their positions
        table_titles = []
        table_items = []

        for item in detail:
            page_id = item.get('page_id', 1)
            type_ = item.get('type')
            sub_type = item.get('sub_type')
            text = item.get('text', '')
            position = item.get('position', [0, 0, 0, 0, 0, 0])

            # Convert coordinates from TextIn (144 dpi) to RAGFlow (72 dpi)
            x0 = position[0] / 2.0 if len(position) > 0 else 0
            y0 = position[1] / 2.0 if len(position) > 1 else 0
            x1 = position[4] / 2.0 if len(position) > 4 else 100
            y1 = position[5] / 2.0 if len(position) > 5 else 100

            relative_page = page_id - 1 - from_page
            position_tag = f'@@{relative_page}\t{x0:.1f}\t{x1:.1f}\t{y0:.1f}\t{y1:.1f}##'

            if type_ == 'image':
                image_items.append({
                    'text': self._clean_markdown(text),
                    'relative_page': relative_page,
                    'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
                    'position_tag': position_tag,
                })
                continue

            if not text:
                continue

            if type_ == 'paragraph' and sub_type == 'table_title':
                title_text = self._clean_markdown(text)
                table_titles.append({
                    'page_id': page_id,
                    'text': title_text,
                    'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
                    'relative_page': relative_page,
                    'position_tag': position_tag
                })

            elif type_ == 'table':
                split_page_ids = item.get('split_section_page_ids', [])
                split_positions = item.get('split_section_positions', [])

                table_items.append({
                    'page_id': page_id,
                    'text': text,
                    'relative_page': relative_page,
                    'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
                    'split_page_ids': split_page_ids,
                    'split_positions': split_positions,
                    'from_page': from_page
                })

            elif type_ == 'paragraph' and sub_type in ['catalog', 'header', 'footer', 'sidebar', 'text', 'text_title', 'image_title']:
                clean_text = self._clean_markdown(text)
                sections.append((clean_text, position_tag, sub_type))

        # Match titles with tables based on position
        title_table_map = {}

        for i, title in enumerate(table_titles):
            best_table = None
            min_distance = float('inf')
            title_height = max(title['y1'] - title['y0'], 10)  # Minimum height of 10

            for j, table in enumerate(table_items):
                if title['page_id'] == table['page_id']:
                    # Same page: check vertical distance
                    distance = table['y0'] - title['y1']
                    if -title_height < distance < title_height * 4:
                        if abs(distance) < min_distance:
                            min_distance = abs(distance)
                            best_table = j
                elif title['page_id'] == table['page_id'] - 1:
                    # Cross-page: table at top of next page
                    if table['y0'] < title_height * 4:
                        if table['y0'] < min_distance:
                            min_distance = table['y0']
                            best_table = j

            if best_table is not None:
                title_table_map[i] = best_table

        # Process tables
        for j, table_item in enumerate(table_items):
            html = self._process_table_html(table_item['text'])

            relative_page = table_item['relative_page']
            x0, x1, y0, y1 = table_item['x0'], table_item['x1'], table_item['y0'], table_item['y1']

            # Handle split tables
            split_page_ids = table_item.get('split_page_ids', [])
            split_positions = table_item.get('split_positions', [])
            from_page = table_item.get('from_page', 0)

            positions = []

            if split_page_ids and split_positions:
                for split_page_id, split_pos in zip(split_page_ids, split_positions):
                    if len(split_pos) >= 8:
                        split_x0 = split_pos[0] / 2.0
                        split_y0 = split_pos[1] / 2.0
                        split_x1 = split_pos[4] / 2.0
                        split_y1 = split_pos[5] / 2.0
                    else:
                        split_x0 = split_pos[0] / 2.0 if len(split_pos) > 0 else 0
                        split_y0 = split_pos[1] / 2.0 if len(split_pos) > 1 else 0
                        split_x1 = split_pos[4] / 2.0 if len(split_pos) > 4 else 100
                        split_y1 = split_pos[5] / 2.0 if len(split_pos) > 5 else 100

                    split_relative_page = split_page_id - 1 - from_page
                    positions.append((split_relative_page, split_x0, split_x1, split_y0, split_y1))
            else:
                positions = [(relative_page, x0, x1, y0, y1)]

            # Check if this table has a matching title
            matching_title_idx = None
            for title_idx, table_idx in title_table_map.items():
                if table_idx == j:
                    matching_title_idx = title_idx
                    break

            if matching_title_idx is not None:
                title = table_titles[matching_title_idx]
                title_text = title['text']

                # Add caption to HTML
                if '<table' in html:
                    pattern = r'(<table[^>]*>)'
                    match = re.search(pattern, html)
                    if match:
                        table_tag = match.group(1)
                        html = html.replace(table_tag, f'{table_tag}\n<caption>{title_text}</caption>\n', 1)
                    else:
                        html = html.replace('<table', f'<table>\n<caption>{title_text}</caption', 1)
                else:
                    html = f'<table>\n<caption>{title_text}</caption>\n{html}\n</table>'

                # Insert title position at the beginning
                positions.insert(0, (title['relative_page'], title['x0'], title['x1'], title['y0'], title['y1']))

            tables.append(((None, html), positions))

        # Add unmatched titles as regular text
        for i, title in enumerate(table_titles):
            if i not in title_table_map:
                sections.append((title['text'], title['position_tag'], 'text'))

        return sections, tables, image_items

    def _convert_to_boxes(self, sections, from_page, zoomin):
        """Convert TextIn sections to RAGFlow boxes format."""
        self.boxes = []

        temp_boxes = []
        page_heights = {}

        for item in sections:
            if len(item) == 3:
                text, tag, sub_type = item
            else:
                text, tag = item
                sub_type = None

            match = re.search(r'@@([\d-]+)\t([\d.]+)\t([\d.]+)\t([\d.]+)\t([\d.]+)##', tag)
            if not match:
                continue

            page_offset, x0, x1, y0, y1 = match.groups()
            page_num = int(page_offset) + 1

            box = {
                "text": text,
                "page_number": page_num,
                "x0": float(x0),
                "x1": float(x1),
                "top": float(y0),
                "bottom": float(y1),
                "layout_type": "",
            }

            if sub_type == 'text_title':
                box["layout_type"] = "title"

            temp_boxes.append(box)

            page_idx = page_num - 1
            if page_idx not in page_heights:
                page_heights[page_idx] = []
            height = float(y1) - float(y0)
            if height > 0:
                page_heights[page_idx].append(height)

        # Calculate mean heights
        max_page = max(page_heights.keys()) + 1 if page_heights else 1
        self.mean_height = [30] * max_page
        self.mean_width = [8] * max_page

        for page_idx, heights in page_heights.items():
            if heights:
                self.mean_height[page_idx] = np.median(heights)

        self.boxes = temp_boxes

    def _process_tables(self, tables, need_image, zoomin, return_html):
        """Process tables in RAGFlow format."""
        result_tables = []

        for (img, html), positions in tables:
            if need_image and self.page_images and positions:
                # Collect all cropped images for this table
                cropped_images = []
                for page_idx, x0, x1, y0, y1 in positions:
                    if 0 <= page_idx < len(self.page_images):
                        try:
                            page_img = self.page_images[page_idx]
                            left = int(x0 * zoomin)
                            top = int(y0 * zoomin)
                            right = int(x1 * zoomin)
                            bottom = int(y1 * zoomin)

                            left = max(0, left)
                            top = max(0, top)
                            right = min(page_img.size[0], right)
                            bottom = min(page_img.size[1], bottom)

                            if right > left and bottom > top:
                                cropped = page_img.crop((left, top, right, bottom))
                                cropped_images.append(cropped)
                        except Exception as e:
                            logging.warning(f"[TextIn] Failed to crop table image: {e}")

                # Combine all cropped images vertically
                if cropped_images:
                    gap = 6
                    total_height = sum(img.size[1] for img in cropped_images) + gap * (len(cropped_images) - 1)
                    max_width = max(img.size[0] for img in cropped_images)

                    combined = Image.new('RGB', (max_width, total_height), (245, 245, 245))
                    y_offset = 0
                    for cropped_img in cropped_images:
                        combined.paste(cropped_img, (0, y_offset))
                        y_offset += cropped_img.size[1] + gap

                    img = combined

            result_tables.append(((img, html), positions))

        return result_tables

    def _process_images(self, image_items, need_image, zoomin):
        """Process image items, cropping from PDF pages. Returns list of ((img, [txt]), positions)."""
        result = []

        for item in image_items:
            relative_page = item['relative_page']
            x0, y0, x1, y1 = item['x0'], item['y0'], item['x1'], item['y1']
            txt = item['text']
            positions = [(relative_page, x0, x1, y0, y1)]

            img = None
            if need_image and self.page_images and 0 <= relative_page < len(self.page_images):
                try:
                    page_img = self.page_images[relative_page]
                    left = max(0, int(x0 * zoomin))
                    top = max(0, int(y0 * zoomin))
                    right = min(page_img.size[0], int(x1 * zoomin))
                    bottom = min(page_img.size[1], int(y1 * zoomin))
                    if right > left and bottom > top:
                        img = page_img.crop((left, top, right, bottom))
                except Exception as e:
                    logging.warning(f"[TextIn] Failed to crop image: {e}")

            if img is None and not txt:
                continue

            result.append(((img, [txt]), positions))

        return result

    def _simple_text_merge(self):
        """Text merging to combine adjacent blocks."""
        if not self.boxes:
            return

        self.boxes = sorted(self.boxes, key=lambda b: (b["page_number"], b["top"], b["x0"]))

        merged = []
        i = 0
        while i < len(self.boxes):
            box = self.boxes[i]

            is_table = '<table' in box["text"].lower()
            is_title = box.get("layout_type") == "title"

            if is_table or is_title:
                merged.append(box)
                i += 1
                continue

            merged_text = box["text"]
            merged_bottom = box["bottom"]
            merged_x1 = box["x1"]
            merged_x0 = box["x0"]
            j = i + 1

            page_idx = box["page_number"] - 1
            mean_height = self.mean_height[page_idx] if page_idx < len(self.mean_height) else 20

            while j < len(self.boxes):
                next_box = self.boxes[j]

                if next_box["page_number"] != box["page_number"]:
                    break

                if '<table' in next_box["text"].lower() or next_box.get("layout_type") == "title":
                    break

                gap = next_box["top"] - merged_bottom

                if gap < 0 or gap > mean_height * 1.5:
                    break

                text_strip = merged_text.strip()
                if text_strip and text_strip[-1] in '。！？.!?':
                    break

                overlap = min(box["x1"], next_box["x1"]) - max(box["x0"], next_box["x0"])
                box_width = min(box["x1"] - box["x0"], next_box["x1"] - next_box["x0"])
                if box_width > 0 and overlap / box_width < 0.5:
                    break

                merged_text = (merged_text.rstrip() + " " + next_box["text"].lstrip()).strip()
                merged_bottom = next_box["bottom"]
                merged_x0 = min(merged_x0, next_box["x0"])
                merged_x1 = max(merged_x1, next_box["x1"])
                j += 1

            merged_box = {
                "text": merged_text,
                "page_number": box["page_number"],
                "x0": merged_x0,
                "x1": merged_x1,
                "top": box["top"],
                "bottom": merged_bottom,
                "layout_type": box.get("layout_type", "")
            }

            merged.append(merged_box)
            i = j

        self.boxes = merged

    def _clean_markdown(self, text):
        """Remove markdown formatting."""
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        text = re.sub(r'!\[.*?\]\((.*?)\)', '', text)
        return text

    def _process_table_html(self, text):
        """Process table HTML."""
        text = text.replace('<br>', ' ')
        text = text.replace('border="1"', '')
        return text

    def _line_tag(self, box, zoomin):
        """Generate position tag for a box."""
        page_num = box["page_number"] - 1
        return f"@@{page_num}\t{box['x0']:.1f}\t{box['x1']:.1f}\t{box['top']:.1f}\t{box['bottom']:.1f}##"

    @staticmethod
    def remove_tag(txt):
        """Remove position tags from text."""
        return re.sub(r'@@[0-9.\t-]+##', '', txt)

    def crop(self, ck, need_position=False):
        """Crop image based on position tags."""
        if not self.page_images:
            return (None, []) if need_position else None

        positions = []
        for match in re.finditer(r'@@(\d+)\t([\d.]+)\t([\d.]+)\t([\d.]+)\t([\d.]+)##', ck):
            page, x0, x1, y0, y1 = match.groups()
            page = int(page)
            if 0 <= page < len(self.page_images):
                positions.append((page, float(x0), float(x1), float(y0), float(y1)))

        if not positions:
            return (None, []) if need_position else None

        images = []
        final_positions = []
        for page, x0, x1, y0, y1 in positions:
            page_img = self.page_images[page]
            zoomin = 3
            left = int(x0 * zoomin)
            top = int(y0 * zoomin)
            right = int(x1 * zoomin)
            bottom = int(y1 * zoomin)

            left = max(0, left)
            top = max(0, top)
            right = min(page_img.size[0], right)
            bottom = min(page_img.size[1], bottom)

            if right > left and bottom > top:
                images.append(page_img.crop((left, top, right, bottom)))
                final_positions.append((page, x0, x1, y0, y1))

        if not images:
            return (None, []) if need_position else None

        gap = 6
        total_height = sum(img.size[1] for img in images) + gap * (len(images) - 1)
        max_width = max(img.size[0] for img in images)

        combined = Image.new('RGB', (max_width, total_height), (245, 245, 245))
        y_offset = 0
        for img in images:
            combined.paste(img, (0, y_offset))
            y_offset += img.size[1] + gap

        if need_position:
            return combined, final_positions
        return combined