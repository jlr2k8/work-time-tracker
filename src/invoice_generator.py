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
			from . import track_work
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
					
					# Hours breakdown - show weighted contributions when both exist
					if comment_hours > 0 and commit_hours > 0:
						# Both exist - show weighted contributions (90% comment, 10% commit)
						comment_contribution = comment_hours * 0.9
						commit_contribution = commit_hours * 0.1
						hours_text = f"Hours: {comment_hours:.2f}h comments (90% = {comment_contribution:.2f}h)"
						hours_text += f" + {commit_hours:.2f}h commits (10% = {commit_contribution:.2f}h)"
						hours_text += f" = {total_hours:.2f}h total"
					elif comment_hours > 0:
						# Only comment hours
						hours_text = f"Hours: {comment_hours:.2f}h mentioned in Trello comments = {total_hours:.2f}h total"
					elif commit_hours > 0:
						# Only commit hours
						hours_text = f"Hours: {commit_hours:.2f}h commits = {total_hours:.2f}h total"
					else:
						hours_text = f"Hours: {total_hours:.2f}h total"
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
					
					# Ensure circular shape
					ax.set_aspect('equal')
					plt.axis('equal')
					plt.tight_layout(pad=1.5, rect=[0, 0, 1, 1])
					# Save with fixed aspect ratio (no tight bbox for pie charts)
					fd, img_path = tempfile.mkstemp(suffix='.png', prefix='hours_breakdown_')
					os.close(fd)
					fig.savefig(img_path, dpi=150, bbox_inches=None, facecolor='white', pad_inches=0.2)
					self._temp_images.append(img_path)
					# Keep image and label together, use smaller size
					chart_elements = [
						Paragraph("<b>Hours Breakdown</b><br/><p>This chart shows the breakdown of total work hours. Billed hours are from line items on this invoice (calculated using weighted average of comment hours and commit hours). Not Billed hours are from unmatched commits or cards that weren't included in that invoice.</p>", self.styles['InvoiceHeader']),
						Spacer(1, 0.1*inch),
						Image(img_path, width=5*inch, height=5*inch)  # Maintain square aspect ratio
					]
					story.append(KeepTogether(chart_elements))
					story.append(Spacer(1, 0.3*inch))
					plt.close(fig)
			
			# 2. Hours by Card Bar Chart (All cards)
			# Only show cards that are actually in line_items (billed items)
			if stats.get('trello_enabled') and 'estimation_details' in stats:
				details = stats['estimation_details']
				matched_cards = details.get('matched_cards', [])
				
				# Create set of task numbers from line_items (billed items only)
				from . import track_work
				billed_task_nums = {item.get('task_number', '') for item in line_items}
				
				# Get all cards by hours - ONLY from billed items
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
				
				# Sort by hours (highest first)
				card_data.sort(key=lambda x: x[1], reverse=True)
				
				if card_data:
					# Adjust figure height based on number of cards
					# Cap at 7 inches to ensure title + chart fit on one page
					# (Page height: 11" - 1.5" margins = 9.5", title ~0.3", spacing ~0.1", buffer ~1.5" = ~7" max)
					num_cards = len(card_data)
					calculated_height = max(4.5, min(12.0, 0.4 * num_cards + 2.0))
					max_height = 7.0  # Maximum height to keep title and chart together
					height = min(calculated_height, max_height)
					
					# If we had to shrink, reduce bar spacing and font size to fit more cards
					scale_factor = height / calculated_height if calculated_height > max_height else 1.0
					fig, ax = plt.subplots(figsize=(6, height))
					cards, hours = zip(*card_data) if card_data else ([], [])
					
					# Adjust font sizes based on scale factor
					label_fontsize = max(6, int(7 * scale_factor))
					value_fontsize = max(6, int(7 * scale_factor))
					
					bars = ax.barh(range(len(cards)), hours, color='#3498db', height=0.7 * scale_factor)
					ax.set_yticks(range(len(cards)))
					ax.set_yticklabels(cards, fontsize=label_fontsize)
					ax.set_xlabel('Hours', fontsize=9, fontweight='bold')
					ax.invert_yaxis()  # Top card at top
					
					# Calculate max hours and set x-axis limit with padding for text labels
					max_hours = max(hours) if hours else 0
					# Add 15% padding to accommodate text labels
					ax.set_xlim(0, max_hours * 1.15)
					
					# Add value labels on bars
					for i, (bar, hour) in enumerate(zip(bars, hours)):
						width = bar.get_width()
						ax.text(width + 0.1, bar.get_y() + bar.get_height()/2, 
							   f'{hour:.1f}h', ha='left', va='center', fontsize=value_fontsize)
					
					# Reduce padding, especially top margin, to bring chart closer to title
					plt.tight_layout(pad=0.3, h_pad=0.5, w_pad=0.5)
					img_path = self._save_temp_image(fig, 'hours_by_card')
					self._temp_images.append(img_path)
					# Keep image and label together - adjust image height to match figure
					chart_elements = [
						Paragraph("<b>Hours by Card</b>", self.styles['InvoiceHeader']),
						Spacer(1, 0.05*inch),  # Reduced spacing between title and chart
						Image(img_path, width=6*inch, height=height*inch)  # Dynamic height
					]
					story.append(KeepTogether(chart_elements))
					story.append(Spacer(1, 0.3*inch))
					plt.close(fig)
			
			# 3. Daily Work Distribution
			# Calculate per-card first (matching invoice logic), then sum by date
			daily_hours = defaultdict(float)  # Initialize here for both paths
			if stats.get('trello_enabled') and 'estimation_details' in stats:
				details = stats['estimation_details']
				matched_cards = details.get('matched_cards', [])
				
				# Calculate hours per day per card, then sum (matching invoice calculation)
				
				# Process each card separately to apply weighted average correctly
				for match in matched_cards:
					card = match['card']
					card_commits = match.get('commits', [])
					
					# Get comment hours for this card by date
					card_comment_hours_by_date = self._extract_comment_hours_by_date([card], since_date=None)
					
					# Get commit hours for this card by date
					# Filter out merge pull requests and merge conflict resolutions - they don't represent actual work time
					card_commits_by_date = defaultdict(list)
					msg_lower = lambda c: c.get('message', '').lower()
					non_merge_commits = [
						c for c in card_commits 
						if not ('merge pull request' in msg_lower(c) or 
								'merge pr' in msg_lower(c) or
								msg_lower(c).startswith('merge pull request') or
								msg_lower(c).startswith('merge pr') or
								('merge' in msg_lower(c) and 'branch' in msg_lower(c)) or
								'resolve merge conflict' in msg_lower(c) or
								'merge conflict' in msg_lower(c) or
								'resolved merge conflict' in msg_lower(c) or
								'fix merge conflict' in msg_lower(c))
					]
					for commit in non_merge_commits:
						date = commit.get('date', '')
						if date:
							card_commits_by_date[date].append(commit)
					
					# Calculate commit hours per day for this card
					card_commit_hours_by_date = defaultdict(float)
					for date, day_commits in card_commits_by_date.items():
						total_lines = sum(c.get('lines_changed', 0) for c in day_commits)
						messages = [c.get('message', '').lower() for c in day_commits]
						
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
						
						if total_lines > 0:
							day_commit_hours = max(0.25, total_lines / lines_per_hour)
						else:
							day_commit_hours = 0.25 if len(day_commits) > 0 else 0.0
						
						card_commit_hours_by_date[date] = day_commit_hours
					
					# For each date this card has work, calculate weighted average per card
					all_card_dates = set(card_comment_hours_by_date.keys()) | set(card_commits_by_date.keys())
					for date in all_card_dates:
						card_comment_hours = card_comment_hours_by_date.get(date, 0.0)
						card_commit_hours = card_commit_hours_by_date.get(date, 0.0)
						
						# Apply weighted average per card (same as invoice calculation)
						if card_comment_hours > 0:
							if card_commit_hours > 0:
								# Both exist - use weighted average
								card_total_hours = (card_comment_hours * 0.9) + (card_commit_hours * 0.1)
							else:
								# Only comment hours
								card_total_hours = card_comment_hours
						else:
							# Only commit hours
							card_total_hours = card_commit_hours
						
						# Sum across all cards for this date
						daily_hours[date] += card_total_hours
			elif stats.get('commits'):
				# Fallback: no Trello, use commit-based estimation only
				commits = stats['commits']
				commits_by_date = defaultdict(list)
				non_merge_commits = [c for c in commits if 'merge' not in c.get('message', '').lower()]
				for commit in non_merge_commits:
					date = commit.get('date', '')
					if date:
						commits_by_date[date].append(commit)
				
				# Calculate commit-based hours per day
				for date, day_commits in commits_by_date.items():
					total_lines = sum(c.get('lines_changed', 0) for c in day_commits)
					messages = [c.get('message', '').lower() for c in day_commits]
					
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
					
					if total_lines > 0:
						day_commit_hours = max(0.25, total_lines / lines_per_hour)
					else:
						day_commit_hours = 0.25 if len(day_commits) > 0 else 0.0
					
					daily_hours[date] = day_commit_hours
				
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
			
			# 3b. Daily Hours Timeline (all days including zeros) - only from billed cards
			if stats.get('trello_enabled') and 'estimation_details' in stats:
				details = stats['estimation_details']
				matched_cards = details.get('matched_cards', [])
				
				# Only use cards that are actually billed (in line_items)
				from . import track_work
				billed_task_nums = {item.get('task_number', '') for item in line_items}
				billed_cards = []
				for match in matched_cards:
					card = match['card']
					task_num = track_work.extract_task_number(card) or 'N/A'
					if task_num in billed_task_nums:
						billed_cards.append(match)
				
				if billed_cards:
					# Get comment hours by date from billed cards only
					cards = [match['card'] for match in billed_cards]
					daily_comment_hours_dict = self._extract_comment_hours_by_date(cards, since_date=None)
					
					# Get commit dates from billed cards only
					all_work_dates = set()
					billed_commits = []
					for match in billed_cards:
						commits = match.get('commits', [])
						for commit in commits:
							date = commit.get('date', '')
							if date:
								all_work_dates.add(date)
								billed_commits.append(commit)
					all_work_dates.update(daily_comment_hours_dict.keys())
					
					# Use the full invoice period: from earliest work date to today
					# This ensures we show ALL days, including days with no work
					if all_work_dates:
						start_date_str = min(all_work_dates)
					else:
						# Fallback: use date_range from stats if available
						date_range = stats.get('date_range', {})
						start_date_str = date_range.get('start')
						if not start_date_str:
							# Last resort: use today
							from datetime import datetime
							start_date_str = datetime.now().strftime('%Y-%m-%d')
					
					# End date is today (or latest work date if later)
					from datetime import datetime
					today_str = datetime.now().strftime('%Y-%m-%d')
					if all_work_dates:
						end_date_str = max(max(all_work_dates), today_str)
					else:
						end_date_str = today_str
					
					# Only create graph if we have valid dates
					if start_date_str and end_date_str:
						# Generate all dates in range
						from datetime import datetime, timedelta
						start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
						end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
						
						# Calculate hours per day per card, then sum (matching card billing logic)
						# This ensures weighted average is applied per card first, then summed
						daily_total_hours = defaultdict(float)  # Final daily hours (already weighted)
						
						# Process each card separately to apply weighted average correctly
						for match in billed_cards:
							card = match['card']
							card_commits = match.get('commits', [])
							
							# Get comment hours for this card by date
							card_comment_hours_by_date = self._extract_comment_hours_by_date([card], since_date=None)
							
							# Get commit hours for this card by date
							card_commits_by_date = defaultdict(list)
							non_merge_commits = [c for c in card_commits if 'merge' not in c.get('message', '').lower()]
							for commit in non_merge_commits:
								date = commit.get('date', '')
								if date:
									card_commits_by_date[date].append(commit)
							
							# Calculate commit hours per day for this card
							card_commit_hours_by_date = defaultdict(float)
							for date, day_commits in card_commits_by_date.items():
								total_lines = sum(c.get('lines_changed', 0) for c in day_commits)
								messages = [c.get('message', '').lower() for c in day_commits]
								
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
								
								if total_lines > 0:
									day_commit_hours = max(0.25, total_lines / lines_per_hour)
								else:
									day_commit_hours = 0.25 if len(day_commits) > 0 else 0.0
								
								card_commit_hours_by_date[date] = day_commit_hours
							
							# For each date this card has work, calculate weighted average per card
							all_card_dates = set(card_comment_hours_by_date.keys()) | set(card_commits_by_date.keys())
							for date in all_card_dates:
								card_comment_hours = card_comment_hours_by_date.get(date, 0.0)
								card_commit_hours = card_commit_hours_by_date.get(date, 0.0)
								
								# Apply weighted average per card (same as card billing)
								if card_comment_hours > 0:
									if card_commit_hours > 0:
										# Both exist - use weighted average
										card_total_hours = (card_comment_hours * 0.9) + (card_commit_hours * 0.1)
									else:
										# Only comment hours
										card_total_hours = card_comment_hours
								else:
									# Only commit hours
									card_total_hours = card_commit_hours
								
								# Sum across all cards for this date
								daily_total_hours[date] += card_total_hours
					
					# Generate all dates in range (including days with no work)
					all_dates_in_range = []
					current_date = start_date
					while current_date <= end_date:
						date_str = current_date.strftime('%Y-%m-%d')
						all_dates_in_range.append(date_str)
						current_date += timedelta(days=1)
					
					# Build complete daily hours list - use pre-calculated per-card totals
					# daily_total_hours already has weighted averages applied per card and summed
					complete_daily_hours = []
					for date_str in all_dates_in_range:
						# Get the total hours for this date (already calculated per-card and summed)
						total_hours = daily_total_hours.get(date_str, 0.0)
						complete_daily_hours.append(total_hours)
					
					# Only create graph if we have data
					if all_dates_in_range and (sum(complete_daily_hours) > 0 or len(all_dates_in_range) > 0):
						# Create graph - make width dynamic based on number of dates
						num_dates = len(all_dates_in_range)
						fig, ax = plt.subplots(figsize=(max(8, num_dates * 0.25), 3.5))
						colors = ['#2ecc71' if h > 0 else '#ecf0f1' for h in complete_daily_hours]
						# Draw bars for all days - give 0-hour days tiny height so they're visible
						bar_heights = [h if h > 0 else 0.02 for h in complete_daily_hours]
						bars = ax.bar(range(len(all_dates_in_range)), bar_heights, color=colors, alpha=0.7, edgecolor='#bdc3c7', linewidth=0.5)
						
						ax.set_xlabel('Date', fontsize=9, fontweight='bold')
						ax.set_ylabel('Hours', fontsize=9, fontweight='bold')
						#ax.set_title('Daily Hours Timeline (All Days)', fontsize=10, fontweight='bold', pad=8)
						
						# Set y-axis range to ensure visibility
						max_hours = max(complete_daily_hours) if complete_daily_hours else 0
						if max_hours > 0:
							ax.set_ylim(bottom=0, top=max(max_hours * 1.15, 1.0))
						else:
							ax.set_ylim(bottom=0, top=1.0)  # Show 0-1 range even if no hours
						
						# Set x-axis labels - show ALL dates
						# Format dates for display (e.g., "2025-11-11" -> "11/11")
						tick_labels = []
						for date_str in all_dates_in_range:
							try:
								date_obj = datetime.strptime(date_str, '%Y-%m-%d')
								tick_labels.append(date_obj.strftime('%m/%d'))
							except:
								tick_labels.append(date_str)
						
						# Adjust font size based on number of dates, but show ALL dates
						if num_dates > 30:
							font_size = 5
						elif num_dates > 14:
							font_size = 6
						else:
							font_size = 7
						
						# Set all tick positions and show ALL date labels
						all_tick_positions = list(range(0, num_dates))
						ax.set_xticks(all_tick_positions)
						ax.set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=font_size)
						ax.tick_params(axis='y', labelsize=7)
						ax.grid(True, alpha=0.3, axis='y')
						
						# Add value labels only on bars with hours > 0
						for i, hours in enumerate(complete_daily_hours):
							if hours > 0:
								ax.text(i, hours + 0.05, f'{hours:.1f}h', 
									   ha='center', va='bottom', fontsize=5)
						
						plt.tight_layout(pad=1.5)
						img_path = self._save_temp_image(fig, 'daily_timeline')
						self._temp_images.append(img_path)
					chart_elements = [
						Paragraph("<b>Daily Hours Timeline</b>", self.styles['InvoiceHeader']),
						Spacer(1, 0.1*inch),
						Image(img_path, width=8*inch, height=3.5*inch)
					]
					story.append(KeepTogether(chart_elements))
					story.append(Spacer(1, 0.3*inch))
					plt.close(fig)
			
			# 4. Estimated vs Actual Hours Line Graph
			if stats.get('trello_enabled') and 'estimation_details' in stats:
				details = stats['estimation_details']
				matched_cards = details.get('matched_cards', [])
				
				# Get cards with estimated hours and/or actual hours for comparison
				# Include all cards that have either estimated hours OR total hours (actual work)
				comparison_data = []
				from . import track_work
				billed_task_nums = {item.get('task_number', '') for item in line_items}
				
				for match in matched_cards:
					card = match['card']
					task_num = track_work.extract_task_number(card) or 'N/A'
					
					# Only include cards that are in line_items (billed items)
					if task_num not in billed_task_nums:
						continue
					
					estimated = match.get('estimated_hours') or 0
					total_hours = match.get('total_hours', 0)  # Use total_hours as actual (includes weighted average)
					
					# Include cards that have either estimated hours OR total hours
					if estimated > 0 or total_hours > 0:
						# Get latest commit date for chronological sorting (most recent work)
						commits = match.get('commits', [])
						latest_date = None
						if commits:
							# Get latest commit date (most recent work on this card)
							commit_dates = [c.get('date', '') for c in commits if c.get('date')]
							if commit_dates:
								latest_date = max(commit_dates)
						
						# Fallback to card last activity date if no commits
						if not latest_date:
							latest_date = card.get('dateLastActivity', card.get('dateCreated', ''))
						
						display_name = f"#{task_num}"
						comparison_data.append({
							'name': display_name,
							'estimated': estimated,
							'actual': total_hours,
							'date': latest_date or ''  # For sorting
						})
				
				# Sort chronologically by latest date (oldest first, most recent last)
				comparison_data.sort(key=lambda x: x['date'] if x['date'] else '0000-00-00')
				# Show all cards, not just top 15
				
				if comparison_data:
					fig, ax = plt.subplots(figsize=(7, 4))
					card_names = [d['name'] for d in comparison_data]
					estimated_hours = [d['estimated'] for d in comparison_data]
					actual_hours = [d['actual'] for d in comparison_data]
					
					x_pos = range(len(card_names))
					ax.plot(x_pos, estimated_hours, marker='o', label='Estimated (from title)', 
						   color='#3498db', linewidth=2, markersize=6)
					ax.plot(x_pos, actual_hours, marker='s', label='Actual (total hours)', 
						   color='#2ecc71', linewidth=2, markersize=6)
					
					ax.set_xlabel('Card', fontsize=9, fontweight='bold')
					ax.set_ylabel('Hours', fontsize=9, fontweight='bold')
					# ax.set_title('Estimated vs Actual Hours by Card', fontsize=11, fontweight='bold', pad=10)
					ax.set_xticks(x_pos)
					ax.set_xticklabels(card_names, rotation=45, ha='right', fontsize=7)
					ax.legend(loc='best', fontsize=8)
					ax.grid(True, alpha=0.3)
					ax.tick_params(axis='y', labelsize=7)
					
					# Add value labels on points
					for i, (est, actual) in enumerate(zip(estimated_hours, actual_hours)):
						ax.text(i, est + 0.2, f'{est:.1f}h', ha='center', va='bottom', fontsize=6, color='#3498db')
						ax.text(i, actual - 0.2, f'{actual:.1f}h', ha='center', va='top', fontsize=6, color='#2ecc71')
					
					plt.tight_layout(pad=2.0)
					img_path = self._save_temp_image(fig, 'estimated_vs_actual')
					self._temp_images.append(img_path)
					chart_elements = [
						Paragraph("<b>Estimated vs Actual Hours</b>", self.styles['InvoiceHeader']),
						Spacer(1, 0.1*inch),
						Image(img_path, width=7*inch, height=4*inch)
					]
					story.append(KeepTogether(chart_elements))
					story.append(Spacer(1, 0.3*inch))
					plt.close(fig)
			
			# 5. Category Breakdown Pie Chart
			category_hours = defaultdict(float)
			for item in line_items:
				category = item.get('category', 'MAINT')
				amount = float(item.get('amount', 0))
				hours = amount / config.hourly_rate
				category_hours[category] += hours
			
			if category_hours:
				# Use square figure for pie chart - slightly larger to prevent squeezing
				fig, ax = plt.subplots(figsize=(6, 6))
				categories = list(category_hours.keys())
				hours = list(category_hours.values())
				
				# Use different colors for each category
				colors_pie = plt.cm.Set3(range(len(categories)))
				wedges, texts, autotexts = ax.pie(hours, labels=categories, autopct='%1.1f%%', 
												  startangle=90, colors=colors_pie, textprops={'fontsize': 10})
				
				# Make percentage text bold and readable
				for autotext in autotexts:
					autotext.set_color('white')
					autotext.set_fontweight('bold')
					autotext.set_fontsize(10)
				
				# Improve label text
				for text in texts:
					text.set_fontsize(10)
				
				# Ensure circular shape - set equal aspect and adjust layout
				ax.set_aspect('equal')
				plt.axis('equal')  # Additional safeguard for circular pie chart
				# Use tight_layout with rect parameter to maintain square shape
				plt.tight_layout(pad=2.0, rect=[0, 0, 1, 1])
				# Save with fixed aspect ratio (no tight bbox for pie charts)
				fd, img_path = tempfile.mkstemp(suffix='.png', prefix='category_breakdown_')
				os.close(fd)
				fig.savefig(img_path, dpi=150, bbox_inches=None, facecolor='white', pad_inches=0.2)
				self._temp_images.append(img_path)
				# Keep image and label together - use same size as figure to prevent distortion
				chart_elements = [
					Paragraph("<b>Hours by Category</b><br/><p>This chart shows work categorized by type (Feature, Fix, Maintenance). Categories are determined at the card level based on card labels, names, and commit messages. Cards may contain multiple types of work, which is why you see combined categories like 'FEAT/FIX/MAINT'. Hours shown are from billed line items only.</p>", self.styles['InvoiceHeader']),
					Spacer(1, 0.1*inch),
					Image(img_path, width=6*inch, height=6*inch)  # Match figure size to prevent squeezing
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
	
	def _extract_comment_hours_by_date(self, cards: List[Dict], since_date: str = None) -> Dict[str, float]:
		"""
		Extract comment hours grouped by date from Trello cards
		
		Args:
			cards: List of card dictionaries with 'actions' containing comments
			since_date: Only count comments since this date (YYYY-MM-DD)
			
		Returns:
			Dictionary mapping date strings (YYYY-MM-DD) to total comment hours on that date
		"""
		from .trello_client import TrelloClient
		try:
			from dateutil import parser as date_parser
		except ImportError:
			date_parser = None
		from datetime import datetime
		import re
		
		daily_comment_hours = defaultdict(float)
		
		hour_patterns = [
			r'(?:^|[^\d@])(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',
			r'spent\s+(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',
			r'worked\s+(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',
			r'hours?:\s*(\d+\.?\d*)(?:\s|$|[^\d])',
			r'\[(\d+\.?\d*)\s*h(?:ours?|rs?)\]',
		]
		
		minute_patterns = [
			r'(?:^|[^\d@])(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',
			r'spent\s+(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',
			r'worked\s+(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',
			r'minutes?:\s*(\d+\.?\d*)(?:\s|$|[^\d])',
			r'\[(\d+\.?\d*)\s*(?:min|mins|minutes?)\]',
		]
		
		for card in cards:
			actions = card.get('actions', [])
			comments = [a for a in actions if a.get('type') == 'commentCard']
			
			for comment in comments:
				comment_date_str = comment.get('date', '')
				if not comment_date_str:
					continue
				
				# Parse comment date
				if not date_parser:
					# If dateutil not available, skip date parsing
					continue
				
				try:
					comment_dt = date_parser.parse(comment_date_str)
					comment_date = comment_dt.date().strftime('%Y-%m-%d')
					
					# Filter by since_date if provided
					if since_date:
						try:
							since_dt = datetime.strptime(since_date, '%Y-%m-%d')
							if comment_dt.date() < since_dt.date():
								continue
						except ValueError:
							pass
				except:
					continue
				
				# Extract hours from comment text
				text = comment.get('data', {}).get('text', '')
				if not text:
					continue
				
				# Try hours patterns first
				matched = False
				for pattern in hour_patterns:
					matches = re.findall(pattern, text, re.IGNORECASE)
					if matches:
						try:
							hours = float(matches[0])
							daily_comment_hours[comment_date] += hours
							matched = True
							break
						except ValueError:
							continue
				
				# If no hours found, try minutes patterns
				if not matched:
					for pattern in minute_patterns:
						matches = re.findall(pattern, text, re.IGNORECASE)
						if matches:
							try:
								minutes = float(matches[0])
								hours = round(minutes / 60.0, 2)
								daily_comment_hours[comment_date] += hours
								break
							except ValueError:
								continue
		
		return dict(daily_comment_hours)
	
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
	
	# Ensure output directory exists
	output_dir_path = Path(output_dir)
	output_dir_path.mkdir(parents=True, exist_ok=True)
	
	output_path = output_dir_path / filename
	
	# Get config for breakdown page
	from .config import Config
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

