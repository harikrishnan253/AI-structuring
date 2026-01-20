
from backend.processor.classifier import validate_style_for_zone, ZONE_STYLE_CONSTRAINTS, GeminiClassifier

def test_validation_logic():
    print("Testing validate_style_for_zone...")
    
    # Test valid cases
    assert validate_style_for_zone("CN", "FRONT_MATTER") == True
    assert validate_style_for_zone("PMI", "METADATA") == True
    assert validate_style_for_zone("T", "TABLE") == True
    
    # Test wildcard cases
    assert validate_style_for_zone("NBX-BL-MID", "BOX_NBX") == True
    assert validate_style_for_zone("NBX-BL-CUSTOM", "BOX_NBX") == True
    assert validate_style_for_zone("KT-BL-FIRST", "FRONT_MATTER") == True
    
    # Test invalid cases
    assert validate_style_for_zone("H1", "TABLE") == False
    assert validate_style_for_zone("CN", "BODY") == True # BODY is None -> True
    
    print("Validation logic tests passed!")

def test_constraints_structure():
    print("Testing ZONE_STYLE_CONSTRAINTS structure...")
    assert 'METADATA' in ZONE_STYLE_CONSTRAINTS
    assert 'FRONT_MATTER' in ZONE_STYLE_CONSTRAINTS
    assert ZONE_STYLE_CONSTRAINTS['BODY'] is None
    print("Structure tests passed!")

if __name__ == "__main__":
    try:
        test_validation_logic()
        test_constraints_structure()
        print("All tests passed successfully.")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
