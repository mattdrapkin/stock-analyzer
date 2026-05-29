"""
PDF generation utility for stock analysis reports.
"""

import re
from datetime import datetime, timezone
from typing import Optional
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.colors import blue
from .models import TickerAnalysis, BasketAnalysisResponse


def parse_markdown_to_reportlab(text: str) -> str:
    """
    Convert markdown text to ReportLab-compatible format.
    
    Handles:
    - Links: [text](url) -> <link href="url"><u>text</u></link>
    - Bold: **text** -> <b>text</b>
    - Italic: *text* -> <i>text</i>
    """
    if not text:
        return text
    
    # Escape HTML special characters first
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # Convert markdown links: [text](url) to <link href="url"><u>text</u></link>
    text = re.sub(
        r'\[([^\]]+)\]\(([^\)]+)\)',
        r'<link href="\2" color="blue"><u>\1</u></link>',
        text
    )
    
    # Convert bold: **text** to <b>text</b>
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    
    # Convert italic: *text* to <i>text</i>
    text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
    
    return text


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
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
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
        ["News Source:", analysis.news_source or "N/A"],
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
            # Parse markdown in title and handle links
            parsed_title = parse_markdown_to_reportlab(card.title)
            if card.url:
                title_text = f'{i}. <link href="{card.url}" color="blue"><u>{parsed_title}</u></link>'
            else:
                title_text = f"{i}. {parsed_title}"
            
            story.append(Paragraph(title_text, ParagraphStyle(
                'NewsTitle',
                parent=styles['Normal'],
                fontSize=10,
                fontName='Helvetica-Bold',
                spaceAfter=4,
                textColor=blue if card.url else colors.black,
            )))
            if card.summary:
                parsed_summary = parse_markdown_to_reportlab(card.summary)
                story.append(Paragraph(parsed_summary, ParagraphStyle(
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


def generate_basket_pdf(basket_response: BasketAnalysisResponse, params: dict) -> bytes:
    """
    Generate a PDF report for a basket analysis.
    
    Args:
        basket_response: BasketAnalysisResponse object containing the analysis data
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
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    story.append(Paragraph(f"Report Generated: {timestamp}", normal_style))
    story.append(Spacer(1, 0.2 * inch))
    
    # Title
    ticker_str = ", ".join(basket_response.tickers[:5])
    if len(basket_response.tickers) > 5:
        ticker_str += f" + {len(basket_response.tickers) - 5} more"
    story.append(Paragraph(f"Basket Analysis Report", title_style))
    story.append(Paragraph(f"Tickers: {ticker_str}", ParagraphStyle(
        'Subtitle',
        parent=styles['Heading3'],
        fontSize=14,
        textColor=colors.HexColor('#64748b'),
        alignment=TA_CENTER,
        spaceAfter=20,
    )))
    story.append(Spacer(1, 0.2 * inch))
    
    # Analysis Parameters
    story.append(Paragraph("Analysis Parameters", heading_style))
    param_data = [
        ["Period Start:", str(basket_response.period_start)],
        ["Period End:", str(basket_response.period_end)],
        ["Total Tickers Analyzed:", str(basket_response.total_analyzed)],
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
    up_count = sum(1 for r in basket_response.results if r.direction == "up")
    down_count = len(basket_response.results) - up_count
    stats_data = [
        ["Total Analyzed:", str(basket_response.total_analyzed)],
        ["Up Movements:", str(up_count)],
        ["Down Movements:", str(down_count)],
        ["News Source:", basket_response.news_source or "N/A"],
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
    
    # Basket Performance Table
    story.append(Paragraph("Basket Performance", heading_style))
    if basket_response.results:
        performance_data = [["Ticker", "Company", "Start Price", "End Price", "Change %", "Direction"]]
        for result in basket_response.results:
            performance_data.append([
                result.ticker,
                (result.company_name or "N/A")[:30],  # Truncate long names
                f"${result.start_price:.2f}",
                f"${result.end_price:.2f}",
                f"{result.total_change_pct:+.2f}%",
                result.direction.upper(),
            ])
        
        performance_table = Table(performance_data, colWidths=[1 * inch, 2 * inch, 1 * inch, 1 * inch, 1 * inch, 1 * inch])
        performance_table.setStyle(TableStyle([
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
        story.append(performance_table)
    else:
        story.append(Paragraph("No results available for this basket.", normal_style))
    story.append(Spacer(1, 0.3 * inch))
    
    # Holistic Summary
    if basket_response.holistic_summary:
        story.append(Paragraph("Holistic Summary", heading_style))
        parsed_summary = parse_markdown_to_reportlab(basket_response.holistic_summary)
        story.append(Paragraph(parsed_summary, normal_style))
        story.append(Spacer(1, 0.3 * inch))
    
    # News Highlights by Ticker
    if basket_response.results:
        story.append(Paragraph("News Highlights by Ticker", heading_style))
        for result in basket_response.results:
            if result.news_cards:
                story.append(Paragraph(f"{result.ticker} - {result.company_name or 'N/A'}", ParagraphStyle(
                    'TickerHeading',
                    parent=styles['Heading3'],
                    fontSize=12,
                    textColor=colors.HexColor('#1e3a8a'),
                    spaceAfter=8,
                )))
                for i, card in enumerate(result.news_cards[:5], 1):  # Limit to first 5 articles per ticker
                    # Parse markdown in title and handle links
                    parsed_title = parse_markdown_to_reportlab(card.title)
                    if card.url:
                        title_text = f'{i}. <link href="{card.url}" color="blue"><u>{parsed_title}</u></link>'
                    else:
                        title_text = f"{i}. {parsed_title}"
                    
                    story.append(Paragraph(title_text, ParagraphStyle(
                        'NewsTitle',
                        parent=styles['Normal'],
                        fontSize=10,
                        fontName='Helvetica-Bold',
                        spaceAfter=4,
                        textColor=blue if card.url else colors.black,
                    )))
                    if card.summary:
                        parsed_summary = parse_markdown_to_reportlab(card.summary)
                        story.append(Paragraph(parsed_summary, ParagraphStyle(
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
                story.append(Spacer(1, 0.2 * inch))
    
    # Build PDF
    doc.build(story)
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
