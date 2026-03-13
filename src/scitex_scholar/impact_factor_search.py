#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Impact factor search and journal ranking integration

"""
Impact factor search and journal ranking module.

This module provides functionality to search journals by impact factor,
rank papers by journal quality, and filter results based on journal metrics.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import re
from .paper_acquisition import PaperMetadata

logger = logging.getLogger(__name__)

# Try to import impact-factor package
try:
    from impact_factor.core import Factor, FactorManager
    IMPACT_FACTOR_AVAILABLE = True
    logger.info("✅ Impact factor package imported successfully")
except ImportError as e:
    IMPACT_FACTOR_AVAILABLE = False
    logger.warning(f"⚠️ Impact factor package not available: {e}")
    logger.warning("   Journal ranking features will be limited")


class JournalRankingSearch:
    """Journal ranking and impact factor search functionality."""
    
    def __init__(self):
        """Initialize journal ranking search."""
        self.factor_manager = None
        if IMPACT_FACTOR_AVAILABLE:
            try:
                self.factor_manager = FactorManager()
                logger.info("✅ Impact factor client initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize impact factor client: {e}")
                # Don't modify global variable
    
    def search_journals_by_impact_factor(self, 
                                        min_impact_factor: float = None,
                                        max_impact_factor: float = None,
                                        subject_category: str = None,
                                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search journals by impact factor criteria.
        
        Args:
            min_impact_factor: Minimum impact factor threshold
            max_impact_factor: Maximum impact factor threshold  
            subject_category: Subject category filter (e.g., 'NEUROSCIENCES', 'MEDICINE')
            limit: Maximum number of results
            
        Returns:
            List of journal information dictionaries
        """
        if not IMPACT_FACTOR_AVAILABLE or not self.factor_manager:
            logger.warning("Impact factor search not available")
            return []
        
        try:
            # Get all journals with impact factors
            journals = self.factor_manager.search()
            
            # Apply filters
            filtered_journals = []
            for journal in journals:
                if not journal.get('impact_factor'):
                    continue
                
                impact_factor = float(journal['impact_factor'])
                
                # Apply impact factor range filter
                if min_impact_factor and impact_factor < min_impact_factor:
                    continue
                if max_impact_factor and impact_factor > max_impact_factor:
                    continue
                
                # Apply subject category filter
                if subject_category:
                    categories = journal.get('categories', [])
                    if isinstance(categories, str):
                        categories = [categories]
                    
                    category_match = any(
                        subject_category.lower() in cat.lower() 
                        for cat in categories
                    )
                    if not category_match:
                        continue
                
                filtered_journals.append({
                    'name': journal.get('title', ''),
                    'abbreviation': journal.get('abbreviation', ''),
                    'issn': journal.get('issn', ''),
                    'impact_factor': impact_factor,
                    'categories': categories,
                    'publisher': journal.get('publisher', ''),
                    'quartile': journal.get('quartile', ''),
                    'rank_in_category': journal.get('rank', ''),
                })
            
            # Sort by impact factor (descending)
            filtered_journals.sort(key=lambda x: x['impact_factor'], reverse=True)
            
            return filtered_journals[:limit]
            
        except Exception as e:
            logger.error(f"Error searching journals by impact factor: {e}")
            return []
    
    def get_journal_impact_factor(self, journal_name: str, issn: str = None) -> Optional[float]:
        """
        Get impact factor for a specific journal.
        
        Args:
            journal_name: Name of the journal
            issn: ISSN of the journal (optional, helps with accuracy)
            
        Returns:
            Impact factor as float or None if not found
        """
        if not IMPACT_FACTOR_AVAILABLE or not self.factor_manager:
            return None
        
        try:
            # Try searching by journal name
            factor = Factor(journal_name)
            impact_factor = factor.get_impact_factor()
            
            if impact_factor:
                return float(impact_factor)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting impact factor for {journal_name}: {e}")
            return None
    
    def _fuzzy_match_journal_name(self, query: str, target: str) -> bool:
        """
        Fuzzy match journal names to handle abbreviations and variations.
        
        Args:
            query: Query journal name
            target: Target journal name
            
        Returns:
            True if names likely match
        """
        # Normalize strings
        query = re.sub(r'[^\w\s]', '', query.lower()).strip()
        target = re.sub(r'[^\w\s]', '', target.lower()).strip()
        
        # Direct match
        if query == target:
            return True
        
        # Check if one is contained in the other
        if query in target or target in query:
            return True
        
        # Check key words match (for abbreviated names)
        query_words = set(query.split())
        target_words = set(target.split())
        
        # Remove common words
        common_words = {'of', 'the', 'and', 'in', 'for', 'on', 'journal', 'international'}
        query_words -= common_words
        target_words -= common_words
        
        if not query_words or not target_words:
            return False
        
        # Check if significant overlap
        overlap = len(query_words & target_words)
        return overlap / min(len(query_words), len(target_words)) >= 0.6
    
    def rank_papers_by_journal_quality(self, papers: List[PaperMetadata]) -> List[Tuple[PaperMetadata, float]]:
        """
        Rank papers by their journal impact factors.
        
        Args:
            papers: List of paper metadata
            
        Returns:
            List of (paper, impact_factor) tuples sorted by impact factor
        """
        ranked_papers = []
        
        for paper in papers:
            impact_factor = 0.0
            
            # Get impact factor for the journal
            if paper.journal:
                impact_factor = self.get_journal_impact_factor(paper.journal) or 0.0
            
            ranked_papers.append((paper, impact_factor))
        
        # Sort by impact factor (descending)
        ranked_papers.sort(key=lambda x: x[1], reverse=True)
        
        return ranked_papers
    
    def filter_papers_by_impact_factor(self, 
                                     papers: List[PaperMetadata],
                                     min_impact_factor: float = None,
                                     max_impact_factor: float = None) -> List[PaperMetadata]:
        """
        Filter papers by journal impact factor.
        
        Args:
            papers: List of paper metadata
            min_impact_factor: Minimum impact factor threshold
            max_impact_factor: Maximum impact factor threshold
            
        Returns:
            Filtered list of papers
        """
        if not min_impact_factor and not max_impact_factor:
            return papers
        
        filtered_papers = []
        
        for paper in papers:
            if not paper.journal:
                # Include papers without journal info if no minimum threshold
                if not min_impact_factor:
                    filtered_papers.append(paper)
                continue
            
            impact_factor = self.get_journal_impact_factor(paper.journal)
            
            if impact_factor is None:
                # Include papers with unknown impact factor if no minimum threshold
                if not min_impact_factor:
                    filtered_papers.append(paper)
                continue
            
            # Apply filters
            if min_impact_factor and impact_factor < min_impact_factor:
                continue
            if max_impact_factor and impact_factor > max_impact_factor:
                continue
            
            filtered_papers.append(paper)
        
        return filtered_papers
    
    def get_high_impact_journals(self, subject_category: str = None, top_n: int = 50) -> List[Dict[str, Any]]:
        """
        Get list of high-impact journals in a subject category.
        
        Args:
            subject_category: Subject category filter
            top_n: Number of top journals to return
            
        Returns:
            List of high-impact journal information
        """
        try:
            return self.search_journals_by_impact_factor(
                min_impact_factor=5.0,  # Typically considered high impact
                subject_category=subject_category,
                limit=top_n
            )
        except Exception as e:
            logger.error(f"Error getting high impact journals: {e}")
            return []
    
    def suggest_target_journals(self, 
                              keywords: List[str], 
                              min_impact_factor: float = None) -> List[Dict[str, Any]]:
        """
        Suggest target journals based on research keywords.
        
        Args:
            keywords: List of research keywords
            min_impact_factor: Minimum impact factor threshold
            
        Returns:
            List of suggested journals
        """
        if not keywords:
            return []
        
        try:
            # Search for journals by keywords in categories/scope
            all_journals = self.search_journals_by_impact_factor(
                min_impact_factor=min_impact_factor
            )
            
            # Score journals based on keyword relevance
            scored_journals = []
            for journal in all_journals:
                score = 0
                
                # Check keywords in journal categories
                categories = journal.get('categories', [])
                if isinstance(categories, str):
                    categories = [categories]
                
                category_text = ' '.join(categories).lower()
                journal_name = journal.get('name', '').lower()
                
                for keyword in keywords:
                    keyword = keyword.lower()
                    if keyword in category_text:
                        score += 2
                    if keyword in journal_name:
                        score += 3
                
                if score > 0:
                    journal['relevance_score'] = score
                    scored_journals.append(journal)
            
            # Sort by relevance score and impact factor
            scored_journals.sort(
                key=lambda x: (x['relevance_score'], x['impact_factor']), 
                reverse=True
            )
            
            return scored_journals[:20]  # Return top 20 suggestions
            
        except Exception as e:
            logger.error(f"Error suggesting target journals: {e}")
            return []


# Convenience functions
def search_high_impact_papers(papers: List[PaperMetadata], 
                            min_impact_factor: float = 5.0) -> List[PaperMetadata]:
    """Quick function to filter papers by high impact factor."""
    ranker = JournalRankingSearch()
    return ranker.filter_papers_by_impact_factor(papers, min_impact_factor=min_impact_factor)


def get_journal_impact_factor(journal_name: str, issn: str = None) -> Optional[float]:
    """Quick function to get journal impact factor."""
    ranker = JournalRankingSearch()
    return ranker.get_journal_impact_factor(journal_name, issn)


# EOF