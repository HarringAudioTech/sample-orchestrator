import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlmodel import SQLModel, create_engine, Session
from src.database.models import ProjectModel
from src.core.amanuensis_service import AmanuensisService

def test_integration():
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    
    # Use a temporary SQLite DB for testing
    engine = create_engine("sqlite:///data/test_amanuensis.db")
    SQLModel.metadata.drop_all(engine) # Start fresh
    SQLModel.metadata.create_all(engine)
    db = Session(engine)

    try:
        # 1. Create a dummy project
        project = ProjectModel(name="Amanuensis Test", project_type="sample_pack")
        db.add(project)
        db.commit()
        print(f"Created test project with ID: {project.id}")

        # 2. Initialize AmanuensisService
        service = AmanuensisService(db)

        # 3. Generate a monophonic loop
        print("Generating monophonic loop...")
        mono_result = service.generate_monophonic_loop(
            project_id=project.id,
            label="test_mono_bass",
            engine_id="bass",
            bars=2,
            seed=101,
            max_tweak_passes=1,
            min_loop_fitness=0.3
        )
        print(f"Mono loop generated: {mono_result}")

        # 4. Generate a polyphonic loop
        print("Generating polyphonic loop...")
        poly_result = service.generate_polyphonic_loop(
            project_id=project.id,
            label="test_poly_chords",
            engine_id="kapellmeister",
            bars=4,
            seed=202,
            chords=[{"root": "C", "quality": "major"}, {"root": "F", "quality": "major"}],
            max_tweak_passes=1,
            min_loop_fitness=0.3
        )
        print(f"Poly loop generated: {poly_result}")

        # 5. Generate variations
        print("Generating variations...")
        vars_result = service.generate_variations(
            project_id=project.id,
            label="test_vars",
            engine_id="bass",
            count=3,
            base_seed=303,
            bars=2,
            max_tweak_passes=1,
            min_loop_fitness=0.3
        )
        print(f"Variations generated: {len(vars_result)}")
        for i, var in enumerate(vars_result):
            print(f"  Variation {i+1}: {var['filename']}")

        # 6. Verify files exist on disk
        if Path(mono_result["file_path"]).exists():
            print(f"SUCCESS: Mono MIDI file exists at {mono_result['file_path']}")
        else:
            print(f"FAILURE: Mono MIDI file NOT found at {mono_result['file_path']}")

        if Path(poly_result["file_path"]).exists():
            print(f"SUCCESS: Poly MIDI file exists at {poly_result['file_path']}")
        else:
            print(f"FAILURE: Poly MIDI file NOT found at {poly_result['file_path']}")
            
        for var in vars_result:
            if Path(var["file_path"]).exists():
                print(f"SUCCESS: Variation file exists at {var['file_path']}")
            else:
                print(f"FAILURE: Variation file NOT found at {var['file_path']}")

    finally:
        db.close()

if __name__ == "__main__":
    test_integration()
