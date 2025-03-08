"""Statistics tracking and activity logging.

This module provides functions for generating statistics and
logging activity related to email processing.
"""

import logging
import time
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime

from app.email.models.processed_email import ProcessedEmail
from app.email.pipeline.orchestrator import AnalysisCommand
from app.models.activity import log_activity
from app.utils.memory_profiling import log_memory_usage


async def generate_final_stats(
    stats: Dict,
    logger: Optional[logging.Logger] = None
) -> AsyncGenerator[Dict, None]:
    """Generate and yield final pipeline statistics.
    
    Args:
        stats: Dictionary of processing statistics
        logger: Optional logger for logging events
        
    Yields:
        Final statistics and completion status messages
    """
    logger = logger or logging.getLogger(__name__)
    
    # Calculate success rates
    success_rate_parse = f"{stats['successfully_parsed']}/{stats['new_emails']}" if stats['new_emails'] > 0 else "N/A"
    success_rate_analyze = f"{stats['successfully_analyzed']}/{stats['successfully_parsed']}" if stats['successfully_parsed'] > 0 else "N/A"
    
    # Log final pipeline stats
    logger.info(f"Pipeline Complete: {stats['emails_fetched']} total emails, {stats['new_emails']} new")
    logger.info(f"Pipeline Success Stats: {stats['successfully_parsed']}/{stats['new_emails']} parsed, {stats['successfully_analyzed']}/{stats['new_emails']} analyzed\n")
    logger.debug(f"Pipeline Complete\n"
        f"Email Processing Summary:\n"
        f"    Total Processed: {stats['emails_fetched']} emails\n"
        f"    New Emails: {stats['new_emails']} emails\n"
        f"    Success Rates:\n"
        f"        Parsing: {success_rate_parse}\n"
        f"        Analysis: {success_rate_analyze}"
    )

    # Log memory at end of pipeline
    log_memory_usage(logger, "Pipeline End")

    # Yield completion status
    yield {
        'type': 'complete',
        'data': {
            'processed': stats.get("processed", 0),
            'cached': stats.get("cached", 0),
            'total': stats.get("cached", 0) + stats.get("processed", 0),
        }
    }

    # Yield detailed final stats
    yield {
        'type': 'stats',
        'data': {
            'total_processed': stats.get('emails_fetched', 0),
            'new_emails': stats.get('new_emails', 0),
            'successfully_parsed': stats.get('successfully_parsed', 0),
            'successfully_analyzed': stats.get('successfully_analyzed', 0),
            'failed_parsing': stats.get('failed_parsing', 0),
            'failed_analysis': stats.get('failed_analysis', 0),
            'success_rate_parse': success_rate_parse,
            'success_rate_analyze': success_rate_analyze,
            'batches': stats.get('batches', 0),
            'total': stats.get('cached', 0) + stats.get('processed', 0)
        }
    }


def log_activity(
    user_id: int,
    filtered_emails: List[ProcessedEmail],
    stats: Dict,
    command: AnalysisCommand,
    logger: Optional[logging.Logger] = None
) -> None:
    """Log email analysis activity for a user.
    
    Args:
        user_id: The user's ID
        filtered_emails: List of filtered email results
        stats: Dictionary of processing statistics
        command: The original analysis command
        logger: Optional logger for logging events
    """
    logger = logger or logging.getLogger(__name__)
    
    try:
        start_time = time.time()
        log_activity(
            user_id=user_id,
            activity_type='email_analysis',
            description=f"Analyzed {len(filtered_emails)} emails",
            metadata={
                'analysis_stats': {
                    'total_fetched': stats.get('emails_fetched', 0),
                    'new_emails': stats.get('new_emails', 0),
                    'cached_emails': stats.get('cached', 0),
                    'successfully_parsed': stats.get('successfully_parsed', 0),
                    'successfully_analyzed': stats.get('successfully_analyzed', 0),
                    'failed_parsing': stats.get('failed_parsing', 0),
                    'failed_analysis': stats.get('failed_analysis', 0),
                    'categories': {
                        'Work': sum(1 for email in filtered_emails if email.category == 'Work'),
                        'Personal': sum(1 for email in filtered_emails if email.category == 'Personal'),
                        'Promotions': sum(1 for email in filtered_emails if email.category == 'Promotions'),
                        'Informational': sum(1 for email in filtered_emails if email.category == 'Informational')
                    },
                    'priority_levels': {
                        'HIGH': sum(1 for email in filtered_emails if email.priority_level == 'HIGH'),
                        'MEDIUM': sum(1 for email in filtered_emails if email.priority_level == 'MEDIUM'),
                        'LOW': sum(1 for email in filtered_emails if email.priority_level == 'LOW')
                    },
                    'needs_action': sum(1 for email in filtered_emails if email.needs_action),
                    'has_deadline': sum(1 for email in filtered_emails if any(item.get('due_date') for item in email.action_items)),
                    'processing_time': time.time() - start_time
                },
                'analysis_params': {
                    'days_back': command.days_back,
                    'cache_duration_days': command.cache_duration_days,
                    'batch_size': command.batch_size,
                    'priority_threshold': command.priority_threshold,
                    'categories': command.categories,
                    'timestamp': datetime.now().isoformat()
                }
            }
        )
        logger.info(f"Successfully logged activity for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log pipeline activity: {e}")
