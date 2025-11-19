#!/usr/bin/env python3
"""
Invoice PDF Generator - Creates professional invoices matching the specified format
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import re
import tempfile
import os
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import defaultdict

class InvoiceGenerator:
	"""Generate PDF invoices in the specified format"""
	
	def __init__(self, 
				 sender_name: str = "Your Name",
				 sender_address: str = "123 Main St, City, ST 12345",
				 sender_phone: str = "555-555-5555",
				 sender_email: str = "your.email@example.com",
				 recipient_name: str = "Client Name",
				 invoice_prefix: str = "INV"):
		"""
		Initialize invoice generator with sender/recipient info
		
		Args:
			sender_name: Name of the sender
			sender_address: Sender's address
			sender_phone: Sender's phone number
			sender_email: Sender's email
			recipient_name: Name of the recipient
			invoice_prefix: Prefix for invoice numbers (e.g., "INV")
		"""
		self.sender_name = sender_name
		self.sender_address = sender_address
		self.sender_phone = sender_phone
		self.sender_email = sender_email
		self.recipient_name = recipient_name
		self.invoice_prefix = invoice_prefix
		self.styles = getSampleStyleSheet()
		self._setup_custom_styles()
	
	def _setup_custom_styles(self):
		"""Setup custom paragraph styles"""
		self.styles.add(ParagraphStyle(
			name='InvoiceTitle',
			parent=self.styles['Heading1'],
			fontSize=24,
			textColor=colors.HexColor('#000000'),
			spaceAfter=30,
			alignment=TA_LEFT
		))
		
		self.styles.add(ParagraphStyle(
			name='InvoiceHeader',
			parent=self.styles['Normal'],
			fontSize=10,
			textColor=colors.HexColor('#000000'),
			spaceAfter=12
		))
		
		self.styles.add(ParagraphStyle(
			name='LineItem',
			parent=self.styles['Normal'],
			fontSize=9,
			textColor=colors.HexColor('#000000'),
			spaceAfter=6,
			wordWrap='CJK'  # Enable word wrapping
		))
		
		self.styles.add(ParagraphStyle(
			name='LineItemWrap',
			parent=self.styles['Normal'],
			fontSize=9,
			textColor=colors.HexColor('#000000'),
			spaceAfter=6,
			wordWrap='CJK',
			leftIndent=12  # Indent for nested items
		))
	
	def generate_invoice_number(self, invoice_num: int) -> str:
		"""Generate invoice number in format INV-001"""
		return f"{self.invoice_prefix}-{invoice_num:03d}"
	
	def create_invoice(self, 
					   line_items: List[Dict],
					   invoice_date: str,
					   invoice_number: int,
					   output_path: str,
					   service_description: str = "Web Development",
					   note: Optional[str] = None,
					   stats: Optional[Dict] = None,
					   config: Optional[object] = None,
					   include_breakdown: bool = False):
		"""
		Create an invoice PDF
		
		Args:
			line_items: List of dicts with keys: task_number, description, category, amount
			invoice_date: Date of invoice (MM/DD/YY format)
			invoice_number: Invoice number (will be formatted as INV-001)
			output_path: Path to save the PDF
			service_description: Description of services (default: "Web Development")
			note: Optional note to add at bottom
		"""
		doc = SimpleDocTemplate(output_path, pagesize=letter,
							   rightMargin=0.75*inch, leftMargin=0.75*inch,
							   topMargin=0.75*inch, bottomMargin=0.75*inch)
		
		# Store breakdown flag for use in add_breakdown_page check
		self._include_breakdown = include_breakdown
		
		# Store temporary image files for cleanup after PDF is built
		self._temp_images = []
		
		story = []
		
		# Invoice number and date (top right)
		inv_num = self.generate_invoice_number(invoice_number)
		header_data = [
			[Paragraph(f"<b>Invoice #:</b> {inv_num}", self.styles['InvoiceHeader']),
			 Paragraph(f"<b>Date:</b> {invoice_date}", self.styles['InvoiceHeader']),
			 Paragraph(f"<b>For:</b> {service_description}", self.styles['InvoiceHeader'])]
		]
		# Reduce header column widths slightly to prevent overflow
		header_table = Table(header_data, colWidths=[2.25*inch, 2.25*inch, 2.25*inch])
		header_table.setStyle(TableStyle([
			('ALIGN', (0, 0), (-1, -1), 'LEFT'),
			('VALIGN', (0, 0), (-1, -1), 'TOP'),
		]))
		story.append(header_table)
		story.append(Spacer(1, 0.3*inch))
		
		# Sender information (left side)
		sender_text = f"""
		<b>{self.sender_name}</b><br/>
		{self.sender_address}<br/>
		{self.sender_phone}<br/>
		{self.sender_email}
		"""
		story.append(Paragraph(sender_text, self.styles['InvoiceHeader']))
		story.append(Spacer(1, 0.2*inch))
		
		# TO: Recipient
		story.append(Paragraph(f"<b>TO:</b>", self.styles['InvoiceHeader']))
		story.append(Paragraph(self.recipient_name, self.styles['InvoiceHeader']))
		story.append(Spacer(1, 0.3*inch))
		
		# Line items table
		table_data = []
		total = 0.0
		
		for item in line_items:
			task_num = item.get('task_number', '')
			description = item.get('description', '')
			# Remove pattern like (T3 - (breakdown)) -> T3 - (breakdown)
			# This handles cases where card names contain (T3 - and create double parentheses
			# Match: (T3 - (something)) and remove the outer parentheses
			# Pattern matches: (T3 - (content)) anywhere in the description
			# The content can contain commas, numbers, spaces, etc. but no closing paren until the end
			description = re.sub(r'\(([Tt]\d+)\s*-\s*\(([^)]+)\)\)', r'\1 - (\2)', description)
			category = item.get('category', '')
			amount = float(item.get('amount', 0))
			total += amount
			
			# Format: #33 - PRO Onboarding & Vetting (FEAT/MAINT): description
			item_text = f"<b>#{task_num}</b> - {description}"
			if category:
				item_text += f" <b>({category})</b>"
			
			table_data.append([
				Paragraph(item_text, self.styles['LineItem']),
				Paragraph(f"${amount:,.2f}", self.styles['LineItem'])
			])
		
		# Add total row
		table_data.append([
			Paragraph("<b>Total</b>", self.styles['LineItem']),
			Paragraph(f"<b>${total:,.2f}</b>", self.styles['LineItem'])
		])
		
		# Page width is 8.5" with 0.75" margins = 7" usable width
		# Reduce description column to prevent overflow
		items_table = Table(table_data, colWidths=[5.0*inch, 1.5*inch])
		items_table.setStyle(TableStyle([
			('ALIGN', (0, 0), (0, -1), 'LEFT'),
			('ALIGN', (1, 0), (1, -1), 'RIGHT'),
			('VALIGN', (0, 0), (-1, -1), 'TOP'),
			('BOTTOMPADDING', (0, 0), (-1, -2), 8),
			('TOPPADDING', (0, 0), (-1, -2), 8),
			('BOTTOMPADDING', (0, -1), (-1, -1), 12),
			('TOPPADDING', (0, -1), (-1, -1), 12),
			('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
			('WORDWRAP', (0, 0), (0, -1), True),  # Enable word wrapping in description column
		]))
		
		story.append(items_table)
		story.append(Spacer(1, 0.3*inch))
		
		# Note section
		if note:
			story.append(Paragraph("<b>Note:</b>", self.styles['InvoiceHeader']))
			story.append(Paragraph(note, self.styles['LineItem']))
		else:
			story.append(Paragraph("<b>Note:</b>", self.styles['InvoiceHeader']))
			story.append(Spacer(1, 0.2*inch))
		
		# Add detailed breakdown page if stats provided and flag is set
		if stats and config and getattr(self, '_include_breakdown', False):
			self.add_breakdown_page(story, stats, line_items, config)
		
		# Build PDF
		try:
			doc.build(story)
		finally:
			# Clean up temporary image files after PDF is built
			for img_path in getattr(self, '_temp_images', []):
				try:
					if os.path.exists(img_path):
						os.remove(img_path)
				except:
					pass
		
		return output_path
	
	def add_breakdown_page(self, story: List, stats: Dict, line_items: List[Dict], config):
		"""
		Add a detailed breakdown page showing work details, commit matching, and calculations
		
		Args:
			story: List to append PDF elements to
			stats: Statistics from get_commit_stats()
			line_items: List of invoice line items
			config: Config object with hourly rate
		"""
		story.append(PageBreak())
		
		# Page 2: Detailed Breakdown
		story.append(Paragraph("<b>DETAILED WORK BREAKDOWN</b>", self.styles['InvoiceTitle']))
		story.append(Spacer(1, 0.2*inch))
		
		# Summary statistics
		total_amount = sum(item['amount'] for item in line_items)
		billed_hours = total_amount / config.hourly_rate
		
		summary_data = [
			[Paragraph("<b>Summary</b>", self.styles['InvoiceHeader']), ""],
			[Paragraph(f"Line Items:", self.styles['LineItem']), Paragraph(f"{len(line_items)}", self.styles['LineItem'])],
			[Paragraph(f"Billed Hours:", self.styles['LineItem']), Paragraph(f"{billed_hours:.2f}h", self.styles['LineItem'])],
			[Paragraph(f"Hourly Rate:", self.styles['LineItem']), Paragraph(f"${config.hourly_rate:.2f}", self.styles['LineItem'])],
			[Paragraph(f"<b>Total Amount:</b>", self.styles['LineItem']), Paragraph(f"<b>${total_amount:,.2f}</b>", self.styles['LineItem'])],
		]
		
		if stats.get('trello_enabled') and 'estimation_details' in stats:
			details = stats['estimation_details']
			matched_cards_with_hours = [m for m in details.get('matched_cards', []) if m.get('total_hours', 0) > 0]
			matched_hours = sum(m.get('total_hours', 0) for m in matched_cards_with_hours)
			unmatched_commits = details.get('unmatched_commits', [])
			unmatched_hours = details.get('unmatched_hours', 0)
			total_work_hours = details.get('estimated_hours', 0)
			
			summary_data.extend([
				["", ""],
				[Paragraph("<b>Work Breakdown</b>", self.styles['InvoiceHeader']), ""],
				[Paragraph(f"Trello-matched cards:", self.styles['LineItem']), Paragraph(f"{len(matched_cards_with_hours)} ({matched_hours:.2f}h)", self.styles['LineItem'])],
				[Paragraph(f"Unmatched commits:", self.styles['LineItem']), Paragraph(f"{len(unmatched_commits)} ({unmatched_hours:.2f}h) - NOT BILLED", self.styles['LineItem'])],
				[Paragraph(f"Total work done:", self.styles['LineItem']), Paragraph(f"{total_work_hours:.2f}h", self.styles['LineItem'])],
				[Paragraph(f"Billed:", self.styles['LineItem']), Paragraph(f"{billed_hours:.2f}h (${total_amount:,.2f})", self.styles['LineItem'])],
				[Paragraph(f"Not billed:", self.styles['LineItem']), Paragraph(f"{total_work_hours - billed_hours:.2f}h", self.styles['LineItem'])],
			])
		
		# Reduce column widths to prevent overflow
		summary_table = Table(summary_data, colWidths=[3.75*inch, 2.75*inch])
		summary_table.setStyle(TableStyle([
			('ALIGN', (0, 0), (0, -1), 'LEFT'),
			('ALIGN', (1, 0), (1, -1), 'RIGHT'),
			('VALIGN', (0, 0), (-1, -1), 'TOP'),
			('BOTTOMPADDING', (0, 0), (-1, -1), 4),
			('TOPPADDING', (0, 0), (-1, -1), 4),
		]))
		story.append(summary_table)
		story.append(Spacer(1, 0.3*inch))
		
		# Per-card breakdown
		if stats.get('trello_enabled') and 'estimation_details' in stats:
			details = stats['estimation_details']
			matched_cards = details.get('matched_cards', [])
			
			# Create mapping from task number to matched card data
			# Import here to avoid circular dependency
			import track_work
			task_to_match = {}
			for match in matched_cards:
				card = match['card']
				task_num = track_work.extract_task_number(card) or 'N/A'
				task_to_match[task_num] = match
			
			story.append(Paragraph("<b>Per-Card Breakdown</b>", self.styles['InvoiceHeader']))
			story.append(Spacer(1, 0.15*inch))
			
			for item in line_items:
				task_num = item.get('task_number', '')
				amount = float(item.get('amount', 0))
				
				if task_num in task_to_match:
					match = task_to_match[task_num]
					card = match['card']
					card_name = card.get('name', 'Unknown Task')
					commit_hours = match.get('commit_based_hours', 0)
					comment_hours = match.get('comment_hours', 0)
					total_hours = match.get('total_hours', 0)
					commits = match.get('commits', [])
					
					# Card header - truncate long names but allow wrapping
					# Use shorter truncation to prevent overflow
					card_display = card_name[:60] if len(card_name) > 60 else card_name
					card_text = f"<b>#{task_num} - {card_display}</b>"
					if len(card_name) > 60:
						card_text += "..."
					story.append(Paragraph(card_text, self.styles['LineItem']))
					
					# Hours breakdown
					hours_text = f"Hours: {commit_hours:.2f}h commits"
					if comment_hours > 0:
						hours_text += f" + {comment_hours:.2f}h comments"
					hours_text += f" = {total_hours:.2f}h total"
					story.append(Paragraph(hours_text, self.styles['LineItemWrap']))
					
					# Commit matching info
					if commits:
						explicit_count = len([c for c in commits if c.get('_match_type') == 'explicit'])
						fuzzy_count = len([c for c in commits if c.get('_match_type') == 'fuzzy'])
						match_text = f"Matched {len(commits)} commits ({explicit_count} explicit, {fuzzy_count} fuzzy)"
						story.append(Paragraph(match_text, self.styles['LineItemWrap']))
						
						# Show first 2 commits as examples
						for commit in commits[:2]:
							match_type = commit.get('_match_type', 'unknown')
							msg = commit.get('message', '')[:70]  # Allow longer messages
							lines = commit.get('lines_changed', 0)
							commit_text = f"• [{match_type}] {msg} ({lines:,} lines)"
							story.append(Paragraph(commit_text, self.styles['LineItemWrap']))
						if len(commits) > 2:
							story.append(Paragraph(f"• ... and {len(commits) - 2} more commits", self.styles['LineItemWrap']))
					elif comment_hours > 0:
						story.append(Paragraph("No matching commits (billed from comment hours only)", self.styles['LineItemWrap']))
					
					# Amount
					story.append(Paragraph(f"<b>Amount: ${amount:,.2f}</b>", self.styles['LineItemWrap']))
					story.append(Spacer(1, 0.1*inch))
		
		# Add visualizations at the end
		self._add_visualizations(story, stats, line_items, config)
	
	def _add_visualizations(self, story: List, stats: Dict, line_items: List[Dict], config):
		"""
		Add visual graphs to the breakdown page
		
		Args:
			story: List to append PDF elements to
			stats: Statistics from get_commit_stats()
			line_items: List of invoice line items
			config: Config object with hourly rate
		"""
		story.append(PageBreak())
		story.append(Paragraph("<b>VISUAL SUMMARY</b>", self.styles['InvoiceTitle']))
		story.append(Spacer(1, 0.2*inch))
		
		total_amount = sum(item['amount'] for item in line_items)
		billed_hours = total_amount / config.hourly_rate
		
		# Initialize temp_images list if it doesn't exist
		if not hasattr(self, '_temp_images'):
			self._temp_images = []
		
		try:
			# 1. Hours Breakdown Pie Chart (Billed vs Not Billed)
			if stats.get('trello_enabled') and 'estimation_details' in stats:
				details = stats['estimation_details']
				total_work_hours = details.get('estimated_hours', 0)
				not_billed_hours = total_work_hours - billed_hours
				
				if total_work_hours > 0:
					# Use smaller figure size and maintain aspect ratio
					fig, ax = plt.subplots(figsize=(5, 5))  # Square for pie chart
					labels = ['Billed', 'Not Billed']
					sizes = [billed_hours, max(0, not_billed_hours)]
					colors_pie = ['#2ecc71', '#e74c3c']
					
					# Only show pie chart if there's data
					if billed_hours > 0 or not_billed_hours > 0:
						ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors_pie)
						ax.set_title('Hours Breakdown: Billed vs Not Billed', fontsize=11, fontweight='bold', pad=10)
					
					plt.tight_layout(pad=1.5)
					img_path = self._save_temp_image(fig, 'hours_breakdown')
					self._temp_images.append(img_path)
					# Keep image and label together, use smaller size
					chart_elements = [
						Paragraph("<b>Hours Breakdown</b>", self.styles['InvoiceHeader']),
						Spacer(1, 0.1*inch),
						Image(img_path, width=5*inch, height=5*inch)  # Maintain square aspect ratio
					]
					story.append(KeepTogether(chart_elements))
					story.append(Spacer(1, 0.3*inch))
					plt.close(fig)
			
			# 2. Hours by Card Bar Chart (Top 10 cards)
			# Only show cards that are actually in line_items (billed items)
			if stats.get('trello_enabled') and 'estimation_details' in stats:
				details = stats['estimation_details']
				matched_cards = details.get('matched_cards', [])
				
				# Create set of task numbers from line_items (billed items only)
				import track_work
				billed_task_nums = {item.get('task_number', '') for item in line_items}
				
				# Get top cards by hours - ONLY from billed items
				card_data = []
				for match in matched_cards:
					card = match['card']
					task_num = track_work.extract_task_number(card) or 'N/A'
					
					# Only include cards that are in line_items (billed)
					if task_num not in billed_task_nums:
						continue
					
					card_name = card.get('name', 'Unknown Task')
					total_hours = match.get('total_hours', 0)
					if total_hours > 0:
						# Truncate long card names
						display_name = f"#{task_num}: {card_name[:30]}"
						if len(card_name) > 30:
							display_name += "..."
						card_data.append((display_name, total_hours))
				
				# Sort by hours and take top 10
				card_data.sort(key=lambda x: x[1], reverse=True)
				card_data = card_data[:10]
				
				if card_data:
					# Reduce figure size to fit page
					fig, ax = plt.subplots(figsize=(6, 4.5))
					cards, hours = zip(*card_data) if card_data else ([], [])
					
					bars = ax.barh(range(len(cards)), hours, color='#3498db')
					ax.set_yticks(range(len(cards)))
					ax.set_yticklabels(cards, fontsize=7)
					ax.set_xlabel('Hours', fontsize=9, fontweight='bold')
					ax.set_title('Top Cards by Hours Worked', fontsize=11, fontweight='bold', pad=10)
					ax.invert_yaxis()  # Top card at top
					
					# Add value labels on bars
					for i, (bar, hour) in enumerate(zip(bars, hours)):
						width = bar.get_width()
						ax.text(width + 0.1, bar.get_y() + bar.get_height()/2, 
							   f'{hour:.1f}h', ha='left', va='center', fontsize=7)
					
					plt.tight_layout(pad=1.5)
					img_path = self._save_temp_image(fig, 'hours_by_card')
					self._temp_images.append(img_path)
					# Keep image and label together
					chart_elements = [
						Paragraph("<b>Hours by Card (Top 10)</b>", self.styles['InvoiceHeader']),
						Spacer(1, 0.1*inch),
						Image(img_path, width=6*inch, height=4.5*inch)  # Maintain aspect ratio
					]
					story.append(KeepTogether(chart_elements))
					story.append(Spacer(1, 0.3*inch))
					plt.close(fig)
			
			# 3. Daily Work Distribution
			if stats.get('commits'):
				commits = stats['commits']
				# Group commits by date and calculate hours per day
				daily_hours = defaultdict(float)
				
				# Group commits by date
				commits_by_date = defaultdict(list)
				non_merge_commits = [c for c in commits if 'merge' not in c.get('message', '').lower()]
				for commit in non_merge_commits:
					date = commit.get('date', '')
					if date:
						commits_by_date[date].append(commit)
				
				# Calculate hours per day using same logic as track_work.py
				for date, day_commits in commits_by_date.items():
					total_lines = sum(c.get('lines_changed', 0) for c in day_commits)
					messages = [c.get('message', '').lower() for c in day_commits]
					
					# Determine lines per hour based on complexity
					has_major_feature = any(
						'feature' in msg or 'feat' in msg or 
						'oauth' in msg or 'setup' in msg or
						'refactor' in msg or 'architecture' in msg
						for msg in messages
					)
					has_docs = any('doc' in msg or 'readme' in msg or 'comment' in msg for msg in messages)
					
					if has_major_feature:
						lines_per_hour = 200
					elif has_docs:
						lines_per_hour = 400
					else:
						lines_per_hour = 250
					
					# Calculate hours from lines
					if total_lines > 0:
						day_hours = max(0.25, total_lines / lines_per_hour)
					else:
						day_hours = 0.25 if len(day_commits) > 0 else 0.0
					
					daily_hours[date] = day_hours
				
				if daily_hours:
					# Sort by date
					sorted_dates = sorted(daily_hours.keys())
					dates = sorted_dates[-14:]  # Last 14 days
					hours_list = [daily_hours[d] for d in dates]
					
					# Reduce figure size to fit page
					fig, ax = plt.subplots(figsize=(6, 3.5))
					ax.bar(dates, hours_list, color='#9b59b6', alpha=0.7)
					ax.set_xlabel('Date', fontsize=9, fontweight='bold')
					ax.set_ylabel('Hours', fontsize=9, fontweight='bold')
					ax.set_title('Daily Work Distribution (Last 14 Days)', fontsize=11, fontweight='bold', pad=10)
					ax.tick_params(axis='x', rotation=45, labelsize=7)
					ax.tick_params(axis='y', labelsize=7)
					
					# Add value labels on bars
					for date, hours in zip(dates, hours_list):
						if hours > 0:
							ax.text(date, hours + 0.1, f'{hours:.1f}h', 
								   ha='center', va='bottom', fontsize=6)
					
					plt.tight_layout(pad=1.5)
					img_path = self._save_temp_image(fig, 'daily_distribution')
					self._temp_images.append(img_path)
					# Keep image and label together
					chart_elements = [
						Paragraph("<b>Daily Work Distribution</b>", self.styles['InvoiceHeader']),
						Spacer(1, 0.1*inch),
						Image(img_path, width=6*inch, height=3.5*inch)  # Maintain aspect ratio
					]
					story.append(KeepTogether(chart_elements))
					story.append(Spacer(1, 0.3*inch))
					plt.close(fig)
			
			# 4. Category Breakdown Pie Chart
			category_hours = defaultdict(float)
			for item in line_items:
				category = item.get('category', 'MAINT')
				amount = float(item.get('amount', 0))
				hours = amount / config.hourly_rate
				category_hours[category] += hours
			
			if category_hours:
				# Use square figure for pie chart
				fig, ax = plt.subplots(figsize=(5, 5))
				categories = list(category_hours.keys())
				hours = list(category_hours.values())
				
				# Use different colors for each category
				colors_pie = plt.cm.Set3(range(len(categories)))
				wedges, texts, autotexts = ax.pie(hours, labels=categories, autopct='%1.1f%%', 
												  startangle=90, colors=colors_pie, textprops={'fontsize': 9})
				
				# Make percentage text bold and readable
				for autotext in autotexts:
					autotext.set_color('white')
					autotext.set_fontweight('bold')
					autotext.set_fontsize(9)
				
				# Improve label text
				for text in texts:
					text.set_fontsize(9)
				
				ax.set_title('Hours by Category', fontsize=11, fontweight='bold', pad=10)
				
				plt.tight_layout(pad=1.5)
				img_path = self._save_temp_image(fig, 'category_breakdown')
				self._temp_images.append(img_path)
				# Keep image and label together
				chart_elements = [
					Paragraph("<b>Hours by Category</b>", self.styles['InvoiceHeader']),
					Spacer(1, 0.1*inch),
					Image(img_path, width=5*inch, height=5*inch)  # Maintain square aspect ratio
				]
				story.append(KeepTogether(chart_elements))
				story.append(Spacer(1, 0.3*inch))
				plt.close(fig)
		
		except Exception as e:
			# If there's an error, still try to clean up any images created so far
			for img_path in getattr(self, '_temp_images', []):
				try:
					if os.path.exists(img_path):
						os.remove(img_path)
				except:
					pass
			raise
	
	def _save_temp_image(self, fig, prefix: str) -> str:
		"""
		Save matplotlib figure to temporary file
		
		Args:
			fig: Matplotlib figure
			prefix: Filename prefix
			
		Returns:
			Path to saved image file
		"""
		fd, path = tempfile.mkstemp(suffix='.png', prefix=f'{prefix}_')
		os.close(fd)
		fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
		return path

def create_invoice_from_tracking_data(stats: Dict,
									  line_items: List[Dict],
									  invoice_date: Optional[str] = None,
									  invoice_number: int = 1,
									  output_dir: str = ".",
									  generator: Optional[InvoiceGenerator] = None,
									  include_breakdown: bool = False) -> str:
	"""
	Create an invoice PDF from work tracking data
	
	Args:
		stats: Statistics from get_commit_stats()
		line_items: List of invoice line items with task_number, description, category, amount
		invoice_date: Date in MM/DD/YY format (defaults to today)
		invoice_number: Invoice number
		output_dir: Directory to save invoice
		generator: Optional InvoiceGenerator instance (creates default if None)
	
	Returns:
		Path to generated invoice PDF
	"""
	if generator is None:
		generator = InvoiceGenerator()
	
	if invoice_date is None:
		today = datetime.now()
		invoice_date = today.strftime("%m/%d/%y")
	
	# Generate filename
	inv_num = generator.generate_invoice_number(invoice_number)
	filename = f"invoice_{inv_num.replace('-', '_')}.pdf"
	output_path = Path(output_dir) / filename
	
	# Get config for breakdown page
	from config import Config
	config = Config()
	
	generator.create_invoice(
		line_items=line_items,
		invoice_date=invoice_date,
		invoice_number=invoice_number,
		output_path=str(output_path),
		service_description="Web Development",
		stats=stats,
		config=config,
		include_breakdown=include_breakdown
	)
	
	return str(output_path)

