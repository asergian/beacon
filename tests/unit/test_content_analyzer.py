import pytest
import spacy
from app.email.analyzers.content_analyzer import ContentAnalyzer
from app.email.models.analysis_settings import ProcessingConfig

@pytest.fixture
def nlp():
    try:
        # Try to load the small English model
        return spacy.load("en_core_web_sm")
    except OSError:
        pytest.skip("en_core_web_sm model not installed. Run: python -m spacy download en_core_web_sm")

@pytest.fixture
def analyzer(nlp):
    return ContentAnalyzer(nlp)

def test_analyze_basic(analyzer):
    text = "John Smith needs this report urgently by tomorrow."
    result = analyzer.analyze(text)
    
    assert isinstance(result, dict)
    assert 'entities' in result
    assert 'key_phrases' in result
    assert 'is_urgent' in result

def test_urgency_detection(analyzer):
    # Test with urgent text
    urgent_text = "This is urgent and needs immediate attention"
    result = analyzer.analyze(urgent_text)
    assert result['is_urgent'] == True
    
    # Test without urgent keywords
    normal_text = "This is a regular message"
    result = analyzer.analyze(normal_text)
    assert result['is_urgent'] == False

def test_entity_extraction(analyzer):
    text = "Microsoft and Apple are major tech companies"
    result = analyzer.analyze(text)
    
    assert 'entities' in result
    # Note: Exact matches may vary based on model version
    assert isinstance(result['entities'], dict)

def test_key_phrases_extraction(analyzer):
    text = "The big brown fox jumped over the lazy dog"
    result = analyzer.analyze(text)
    
    assert 'key_phrases' in result
    assert isinstance(result['key_phrases'], list)
    # The small model should identify at least some noun chunks
    assert any('fox' in phrase.lower() for phrase in result['key_phrases'])

def test_empty_text(analyzer):
    result = analyzer.analyze("")
    
    assert result['entities'] == {}
    assert result['key_phrases'] == []
    assert result['is_urgent'] == False

def test_urgency_keywords_configuration():
    # Verify urgency keywords are properly configured
    config = ProcessingConfig()
    assert isinstance(config.URGENCY_KEYWORDS, set)
    assert len(config.URGENCY_KEYWORDS) > 0

def test_analyze_with_special_characters(analyzer):
    text = "Mr. Smith's email (urgent!) needs review by 3:00 PM."
    result = analyzer.analyze(text)
    
    assert isinstance(result['entities'], dict)
    assert isinstance(result['key_phrases'], list)
    # Add debug print to see what's being detected
    print(f"Result: {result}")  # Temporary debug line
    assert result['is_urgent'] == True, "Text containing 'urgent' should be marked as urgent"

def test_urgency_with_punctuation(analyzer):
    # Add new test cases to verify urgency detection with various punctuation
    test_cases = [
        ("This is (urgent)!", True),
        ("URGENT: Please review", True),
        ("This is urgent.", True),
        ("This is (urgent) now", True),
        ("This is urgently needed", True),
        ("Regular message", False),
    ]
    
    for text, expected in test_cases:
        result = analyzer.analyze(text)
        assert result['is_urgent'] == expected, f"Failed for text: {text}" 