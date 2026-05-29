"""
PDF generation utility for stock analysis reports.
"""

from datetime import datetime
from typing import Optional
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.colors import blue
from .models import TickerAnalysis


def generate_analysis_pdf(analysis: TickerAnalysis, params: dict) -> bytes:
    """
    Generate a PDF report for a stock analysis.
    
    Args:
        analysis: TickerAnalysis object containing the analysis data
        params: Dictionary of parameters used for the analysis
        
    Returns:
        bytes: PDF file content
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=12,
    )
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=12,
    )
    
    story = []
    
    # Report generation timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(f"Report Generated: {timestamp}", normal_style))
    story.append(Spacer(1, 0.2 * inch))
    
    # Title
    story.append(Paragraph(f"Stock Analysis Report: {analysis.ticker}", title_style))
    story.append(Spacer(1, 0.2 * inch))
    
    # Company Info
    story.append(Paragraph("Company Information", heading_style))
    company_data = [
        ["Ticker:", analysis.ticker],
        ["Company Name:", analysis.company_name],
        ["Sector:", analysis.sector or "N/A"],
        ["Industry:", analysis.industry or "N/A"],
    ]
    company_table = Table(company_data, colWidths=[2 * inch, 4 * inch])
    company_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(company_table)
    story.append(Spacer(1, 0.3 * inch))
    
    # Analysis Parameters
    story.append(Paragraph("Analysis Parameters", heading_style))
    param_data = [
        ["Period Start:", str(analysis.period_start)],
        ["Period End:", str(analysis.period_end)],
        ["Movement Threshold:", f"±{analysis.min_movement_pct}%"],
        ["Include Competitors:", "Yes" if params.get('include_competitors', False) else "No"],
        ["Include Macro:", "Yes" if params.get('include_macro', False) else "No"],
    ]
    param_table = Table(param_data, colWidths=[2 * inch, 4 * inch])
    param_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(param_table)
    story.append(Spacer(1, 0.3 * inch))
    
    # Summary Statistics
    story.append(Paragraph("Summary Statistics", heading_style))
    stats_data = [
        ["Total Movements:", str(analysis.total_movements)],
        ["Up Movements:", str(analysis.up_movements)],
        ["Down Movements:", str(analysis.down_movements)],
        ["News Source:", analysis.news_source],
    ]
    stats_table = Table(stats_data, colWidths=[2 * inch, 4 * inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 0.3 * inch))
    
    # Significant Movements
    story.append(Paragraph("Significant Price Movements", heading_style))
    if analysis.movements:
        movement_data = [["Date", "Open", "Close", "Change %", "Direction", "Volume"]]
        for move in analysis.movements:
            direction_color = colors.green if move.direction == "up" else colors.red
            movement_data.append([
                str(move.date),
                f"${move.open:.2f}",
                f"${move.close:.2f}",
                f"{move.change_pct:+.2f}%",
                move.direction.upper(),
                f"{move.volume:,}",
            ])
        
        movement_table = Table(movement_data, colWidths=[1.2 * inch, 1 * inch, 1 * inch, 1 * inch, 1 * inch, 1.8 * inch])
        movement_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        story.append(movement_table)
    else:
        story.append(Paragraph("No major movements detected in this period.", normal_style))
    story.append(Spacer(1, 0.3 * inch))
    
    # News Highlights
    if analysis.batch_news_cards and len(analysis.batch_news_cards) > 0:
        story.append(Paragraph(f"News Highlights ({len(analysis.batch_news_cards)} articles)", heading_style))
        for i, card in enumerate(analysis.batch_news_cards[:10], 1):  # Limit to first 10 articles
            # Make title clickable if URL is available
            if card.url:
                title_text = f'{i}. <link href="{card.url}" color="blue">{card.title}</link>'
            else:
                title_text = f"{i}. {card.title}"
            
            story.append(Paragraph(title_text, ParagraphStyle(
                'NewsTitle',
                parent=styles['Normal'],
                fontSize=10,
                fontName='Helvetica-Bold',
                spaceAfter=4,
                textColor=blue if card.url else colors.black,
            )))
            if card.summary:
                story.append(Paragraph(card.summary, ParagraphStyle(
                    'NewsSummary',
                    parent=styles['Normal'],
                    fontSize=9,
                    spaceAfter=8,
                    leftIndent=20,
                )))
            if card.date:
                story.append(Paragraph(f"Date: {card.date} | Source: {card.source_name or 'N/A'}", ParagraphStyle(
                    'NewsMeta',
                    parent=styles['Normal'],
                    fontSize=8,
                    textColor=colors.grey,
                    spaceAfter=12,
                    leftIndent=20,
                )))
            story.append(Spacer(1, 0.1 * inch))
    
    # News note if applicable
    if analysis.news_note:
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(f"Note: {analysis.news_note}", ParagraphStyle(
            'NoteStyle',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            italic=True,
        )))
    
    # Build PDF
    doc.build(story)
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
