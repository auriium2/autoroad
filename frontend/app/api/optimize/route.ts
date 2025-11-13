import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';

const execAsync = promisify(exec);

export async function POST(req: NextRequest) {
  try {
    // Create temp directories if they don't exist
    const tempDir = path.join(process.cwd(), 'temp');
    try {
      await fs.mkdir(tempDir, { recursive: true });
    } catch {
      // Directory might already exist
    }
    
    // Parse the request body
    const requestData = await req.json();
    
    // Generate unique filenames for this request
    const timestamp = new Date().getTime();
    const inputFile = path.join(tempDir, `input_${timestamp}.json`);
    const outputFile = path.join(tempDir, `output_${timestamp}.json`);
    
    // Write the request data to the input file
    await fs.writeFile(inputFile, JSON.stringify(requestData, null, 2), 'utf-8');
    
    // Execute the Python script
    const pythonScript = path.join(process.cwd(), 'analyze_api.py');
    const { stdout, stderr } = await execAsync(
      `python ${pythonScript} --input ${inputFile} --output ${outputFile} --debug`
    );
    
    console.log('Python script output:', stdout);
    
    if (stderr) {
      console.error('Python script error:', stderr);
    }
    
    // Check if the output file was created
    try {
      const outputData = await fs.readFile(outputFile, 'utf-8');
      const result = JSON.parse(outputData);
      
      // Clean up temporary files
      await Promise.all([
        fs.unlink(inputFile).catch(() => {}),
        fs.unlink(outputFile).catch(() => {})
      ]);
      
      return NextResponse.json(result);
    } catch (error) {
      console.error('Error reading output file:', error);
      throw new Error('Failed to read optimization results');
    }
  } catch (error) {
    console.error('Optimization error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to optimize road' }, 
      { status: 500 }
    );
  }
}