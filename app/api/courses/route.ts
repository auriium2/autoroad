import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';

const execAsync = promisify(exec);

// Cache the courses data to avoid repeated fetching
let coursesCache: any = null;
let lastFetchTime = 0;
const CACHE_TTL = 3600000; // 1 hour in milliseconds

export async function GET() {
  try {
    const currentTime = Date.now();
    
    // Return cached data if available and not expired
    if (coursesCache && (currentTime - lastFetchTime < CACHE_TTL)) {
      return NextResponse.json(coursesCache);
    }
    
    // Create temp directory if it doesn't exist
    const tempDir = path.join(process.cwd(), 'temp');
    try {
      await fs.mkdir(tempDir, { recursive: true });
    } catch (err) {
      // Directory might already exist
    }
    
    // Generate unique filename for this request
    const timestamp = currentTime;
    const outputFile = path.join(tempDir, `courses_${timestamp}.json`);
    
    // Execute a Python script to fetch course data
    const pythonScript = path.join(process.cwd(), 'fetch_courses.py');
    
    // Check if the script exists, if not create it
    try {
      await fs.access(pythonScript);
    } catch (err) {
      // Create a simple script to fetch courses
      const scriptContent = `
import requests
import json
import sys

def fetch_courses(output_file):
    try:
        response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
        data = response.json()
        
        # Write to output file
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"Successfully fetched {len(data)} courses")
    except Exception as e:
        print(f"Error fetching courses: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python fetch_courses.py <output_file>", file=sys.stderr)
        sys.exit(1)
        
    output_file = sys.argv[1]
    fetch_courses(output_file)
`;
      await fs.writeFile(pythonScript, scriptContent, 'utf-8');
    }
    
    // Execute the script
    const { stdout, stderr } = await execAsync(`python ${pythonScript} ${outputFile}`);
    
    console.log('Python script output:', stdout);
    
    if (stderr) {
      console.error('Python script error:', stderr);
    }
    
    // Read the output file
    const outputData = await fs.readFile(outputFile, 'utf-8');
    const courses = JSON.parse(outputData);
    
    // Update cache
    coursesCache = courses;
    lastFetchTime = currentTime;
    
    // Clean up the temporary file
    await fs.unlink(outputFile).catch(() => {});
    
    return NextResponse.json(courses);
  } catch (error) {
    console.error('Error fetching courses:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch courses' }, 
      { status: 500 }
    );
  }
}