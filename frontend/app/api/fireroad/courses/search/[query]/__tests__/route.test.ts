/**
 * Tests for Fireroad Course Search API Proxy
 * Tests wildcard behavior, filtering, and pagination
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { GET } from '../route';
import { NextRequest } from 'next/server';
import type { FireroadCourse } from '@/types/models/fireroad';

// Mock the cache module
vi.mock('@/lib/cache', () => ({
  getFullCourseCatalog: vi.fn(),
}));

// Mock the fireroadUtils module
vi.mock('@/lib/fireroadUtils', () => ({
  calculateIMDBRating: vi.fn((rating?: number, enrollment?: number) => {
    if (!rating || !enrollment) return 0;
    return rating;
  }),
}));

import { getFullCourseCatalog } from '@/lib/cache';

const mockCourses: FireroadCourse[] = [
  {
    subject_id: '6.100A',
    title: 'Introduction to Computer Science Programming in Python',
    total_units: 12,
    level: 'U',
    gir_attribute: '',
    hass_attribute: '',
    communication_requirement: '',
    offered_fall: true,
    offered_spring: false,
    offered_IAP: false,
    is_historical: false,
    rating: 4.5,
    enrollment_number: 100,
  },
  {
    subject_id: '6.1200',
    title: 'Mathematics for Computer Science',
    total_units: 12,
    level: 'U',
    gir_attribute: '',
    hass_attribute: '',
    communication_requirement: '',
    offered_fall: true,
    offered_spring: true,
    offered_IAP: false,
    is_historical: false,
    rating: 4.2,
    enrollment_number: 80,
  },
  {
    subject_id: '18.01',
    title: 'Single Variable Calculus',
    total_units: 12,
    level: 'U',
    gir_attribute: 'LAB',
    hass_attribute: '',
    communication_requirement: '',
    offered_fall: true,
    offered_spring: true,
    offered_IAP: false,
    is_historical: false,
    rating: 4.0,
    enrollment_number: 200,
  },
  {
    subject_id: '18.02',
    title: 'Multivariable Calculus',
    total_units: 12,
    level: 'U',
    gir_attribute: '',
    hass_attribute: '',
    communication_requirement: '',
    offered_fall: true,
    offered_spring: true,
    offered_IAP: false,
    is_historical: false,
    rating: 3.8,
    enrollment_number: 150,
  },
  {
    subject_id: '21M.011',
    title: 'Introduction to Western Music',
    total_units: 12,
    level: 'U',
    gir_attribute: '',
    hass_attribute: 'HASS-A',
    communication_requirement: 'CI-H',
    offered_fall: true,
    offered_spring: false,
    offered_IAP: false,
    is_historical: false,
    rating: 4.8,
    enrollment_number: 50,
  },
  {
    subject_id: '6.8300',
    title: 'Advances in Computer Vision',
    total_units: 12,
    level: 'G',
    gir_attribute: '',
    hass_attribute: '',
    communication_requirement: '',
    offered_fall: true,
    offered_spring: false,
    offered_IAP: false,
    is_historical: false,
    rating: 4.5,
    enrollment_number: 30,
  },
];

function createMockRequest(url: string): NextRequest {
  return new NextRequest(new URL(url, 'http://localhost:3000'));
}

describe('Fireroad Course Search Proxy', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getFullCourseCatalog).mockResolvedValue(mockCourses);
  });

  describe('wildcard search (*)', () => {
    it('should return all courses when query is * with no department filter', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(6);
      expect(data.total).toBe(6);
    });

    it('should filter by department when * query is used with department parameter', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?department=6&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(3); // 6.100A, 6.1200, 6.8300
      expect(data.courses.every((c: FireroadCourse) => c.subject_id.startsWith('6.'))).toBe(true);
    });

    it('should apply filters with * query', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?level=G&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(1); // Only 6.8300 is graduate level
      expect(data.courses[0].subject_id).toBe('6.8300');
    });

    it('should apply multiple filters with * query', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?department=6&level=UG&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(2); // 6.100A, 6.1200 (not 6.8300 which is G)
      expect(data.courses.every((c: FireroadCourse) => c.level === 'U')).toBe(true);
    });
  });

  describe('regular search queries', () => {
    it('should search by course ID with starts type', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/6.1?type=starts&offset=0&limit=100');
      const params = Promise.resolve({ query: '6.1' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.length).toBeGreaterThan(0);
      expect(data.courses.every((c: FireroadCourse) => 
        c.subject_id.toLowerCase().startsWith('6.1') ||
        c.title.toLowerCase().startsWith('6.1')
      )).toBe(true);
    });

    it('should search by course ID with contains type', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/math?type=contains&offset=0&limit=100');
      const params = Promise.resolve({ query: 'math' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.length).toBeGreaterThan(0);
      expect(data.courses.some((c: FireroadCourse) => 
        c.subject_id.toLowerCase().includes('math') ||
        c.title.toLowerCase().includes('math')
      )).toBe(true);
    });

    it('should default to contains type when not specified', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/calculus?offset=0&limit=100');
      const params = Promise.resolve({ query: 'calculus' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.length).toBeGreaterThan(0);
    });
  });

  describe('department filtering', () => {
    it('should filter by department with regular query', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/intro?department=6&offset=0&limit=100');
      const params = Promise.resolve({ query: 'intro' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.every((c: FireroadCourse) => c.subject_id.startsWith('6.'))).toBe(true);
    });

    it('should not filter when department is "all"', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/intro?department=all&offset=0&limit=100');
      const params = Promise.resolve({ query: 'intro' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      // Should include courses from multiple departments
    });
  });

  describe('GIR filtering', () => {
    it('should filter by LAB GIR attribute', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?gir=LAB&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(1);
      expect(data.courses[0].subject_id).toBe('18.01');
    });

    it('should filter by REST GIR attribute', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?gir=REST&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(0); // No REST courses in mock data
    });
  });

  describe('HASS filtering', () => {
    it('should filter by HASS attribute', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?hass=HASS-A&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(1);
      expect(data.courses[0].subject_id).toBe('21M.011');
    });
  });

  describe('CI filtering', () => {
    it('should filter by CI-H requirement', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?ci=CI-H&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(1);
      expect(data.courses[0].subject_id).toBe('21M.011');
    });

    it('should filter courses without CI requirement', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?ci=NONE&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.length).toBeGreaterThan(0);
      expect(data.courses.every((c: FireroadCourse) => !c.communication_requirement)).toBe(true);
    });
  });

  describe('level filtering', () => {
    it('should filter undergraduate courses', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?level=UG&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(5); // All U level courses
      expect(data.courses.every((c: FireroadCourse) => c.level === 'U')).toBe(true);
    });

    it('should filter graduate courses', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?level=G&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(1);
      expect(data.courses[0].level).toBe('G');
    });
  });

  describe('units filtering', () => {
    it('should filter courses with exactly 12 units', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?units=12&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.every((c: FireroadCourse) => c.total_units === 12)).toBe(true);
    });

    it('should filter courses with 6+ units', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?units=6%2B&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.every((c: FireroadCourse) => (c.total_units || 0) >= 6)).toBe(true);
    });
  });

  describe('term filtering', () => {
    it('should filter fall courses', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?term=FA&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.every((c: FireroadCourse) => c.offered_fall)).toBe(true);
    });

    it('should filter spring courses', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?term=SP&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.every((c: FireroadCourse) => c.offered_spring)).toBe(true);
    });
  });

  describe('pagination', () => {
    it('should paginate results with offset and limit', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?offset=2&limit=2');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(2);
      expect(data.total).toBe(6);
      expect(data.offset).toBe(2);
      expect(data.limit).toBe(2);
      expect(data.has_more).toBe(true);
    });

    it('should indicate no more results on last page', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?offset=5&limit=2');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses).toHaveLength(1); // Only one course left
      expect(data.has_more).toBe(false);
    });

    it('should use default pagination values', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.offset).toBe(0);
      expect(data.limit).toBe(20);
    });
  });

  describe('error handling', () => {
    it('should return 400 if query is missing', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/?offset=0&limit=20');
      const params = Promise.resolve({ query: '' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(400);
      expect(data.error).toBeDefined();
    });

    it('should return 500 if cache throws error', async () => {
      vi.mocked(getFullCourseCatalog).mockRejectedValue(new Error('Cache error'));
      
      const req = createMockRequest('/api/fireroad/courses/search/*?offset=0&limit=20');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(500);
      expect(data.error).toBeDefined();
    });
  });

  describe('enrichment', () => {
    it('should add IMDB rating to courses', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.every((c: FireroadCourse) => c.imdb_rating !== undefined)).toBe(true);
    });
  });

  describe('sorting', () => {
    it('should sort by IMDB rating ascending', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?sort=imdb-rating-asc&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.length).toBeGreaterThan(0);
      
      for (let i = 0; i < data.courses.length - 1; i++) {
        const current = data.courses[i].imdb_rating ?? 0;
        const next = data.courses[i + 1].imdb_rating ?? 0;
        expect(current).toBeLessThanOrEqual(next);
      }
    });

    it('should sort by IMDB rating descending', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?sort=imdb-rating-desc&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.courses.length).toBeGreaterThan(0);
      
      for (let i = 0; i < data.courses.length - 1; i++) {
        const current = data.courses[i].imdb_rating ?? 0;
        const next = data.courses[i + 1].imdb_rating ?? 0;
        expect(current).toBeGreaterThanOrEqual(next);
      }
    });

    it('should sort by units descending', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?sort=units-desc&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      
      for (let i = 0; i < data.courses.length - 1; i++) {
        const current = data.courses[i].total_units ?? 0;
        const next = data.courses[i + 1].total_units ?? 0;
        expect(current).toBeGreaterThanOrEqual(next);
      }
    });

    it('should sort by enrollment ascending', async () => {
      const req = createMockRequest('/api/fireroad/courses/search/*?sort=enrollment-asc&offset=0&limit=100');
      const params = Promise.resolve({ query: '*' });
      
      const response = await GET(req, { params });
      const data = await response.json();
      
      expect(response.status).toBe(200);
      
      for (let i = 0; i < data.courses.length - 1; i++) {
        const current = data.courses[i].enrollment_number ?? 0;
        const next = data.courses[i + 1].enrollment_number ?? 0;
        expect(current).toBeLessThanOrEqual(next);
      }
    });
  });
});
