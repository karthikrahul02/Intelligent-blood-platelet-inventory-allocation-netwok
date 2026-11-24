import sys
import os
from descriptive_biometrics import run_biometric_analysis

# Check if command-line arguments provided
if len(sys.argv) < 3:
    print("Usage: python run_analysis.py <input_csv_path> <output_directory>")
    print("Example: python run_analysis.py ../test_data_150patients.csv test_data_150patients")
    sys.exit(1)

input_file = sys.argv[1]
output_dir = sys.argv[2]

# Create output directory if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Run the biometric analysis
print(f"Loading data and calculating biometric statistics...")
print(f"Input file: {input_file}")
print(f"Output directory: {output_dir}")

bio = run_biometric_analysis(input_file, output_dir=output_dir)

print(f"\nAnalysis complete! Results saved to:")
print(f"  - {output_dir}/biometric_descriptives.csv")
print(f"  - {output_dir}/biometric_descriptives.txt")
print(f"  - {output_dir}/biometric_descriptives_detailed.json")
