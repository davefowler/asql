"""Shared registries/constants for the ASQL pre-parser."""

from __future__ import annotations

from typing import Dict, Set

FUNCTION_REGISTRY: Set[str] = {
    # Single-word aggregate functions
    'sum', 'avg', 'average', 'total', 'count', 'min', 'max',
    
    # Binning/discretization function
    'bucket',
    
    # Date truncation functions
    'year', 'month', 'week', 'day', 'hour', 'minute', 'second', 'quarter',
    
    # Multi-word date functions
    'day_of_week', 'day_of_month', 'day_of_year',
    'week_of_year', 'month_of_year', 'quarter_of_year',
    'week_monday', 'week_sunday',
    
    # Date difference functions
    'days', 'weeks', 'months', 'years', 'hours', 'minutes', 'seconds',
    'days_between', 'weeks_between', 'months_between', 'years_between',
    
    # String functions
    'upper', 'lower', 'length', 'trim', 'ltrim', 'rtrim',
    'concat', 'substring', 'replace', 'split', 'string_agg',
    
    # Math functions
    'abs', 'round', 'floor', 'ceil', 'ceiling', 'sqrt', 'power',
    
    # Other common functions
    'coalesce', 'nullif', 'cast',
    'date_trunc', 'date_add', 'date_diff', 'date_format',
    
    # Window functions
    'row_number', 'rank', 'dense_rank',
    'lag', 'lead', 'first_value', 'last_value',
    'running_sum', 'running_avg', 'running_count',
    'rolling_sum', 'rolling_avg',
    'prior', 'next',
    
    # Ordered aggregates
    'first', 'last', 'arg_max', 'arg_min',
    
    # Spine control
    'guarantee',  # Explicit spine for a column with optional values
}

# Function aliases
FUNCTION_ALIASES: Dict[str, str] = {
    'total': 'sum',
    'average': 'avg',
    'maximum': 'max',
    'minimum': 'min',
}

# Date units for arithmetic and relative dates
DATE_UNITS: Set[str] = {
    'day', 'days',
    'week', 'weeks', 
    'month', 'months',
    'year', 'years',
    'hour', 'hours',
    'minute', 'minutes',
    'second', 'seconds',
}


