import { describe, it, expect } from 'vitest';
import { buildRequirementTree } from '../requirementTreeBuilder';

describe('requirementTreeBuilder', () => {
  const metadata = {
    title: 'Test Requirement',
    medium: 'Test',
    short: 'Test',
    title_no_degree: 'Test',
  };

  describe('basic course requirements', () => {
    it('should parse a single course requirement', () => {
      const content = '6.100A';
      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.100A', units: 12 },
      ]);

      expect(tree.reqs).toHaveLength(1);
      expect(tree.reqs[0]).toMatchObject({
        req: '6.100A',
        fulfilled: true,
      });
    });

    it('should mark unfulfilled courses', () => {
      const content = '6.100A';
      const tree = buildRequirementTree('test', metadata, 'Description', content, []);

      expect(tree.reqs[0]).toMatchObject({
        req: '6.100A',
        fulfilled: false,
      });
    });

    it('should parse multiple course requirements', () => {
      const content = '6.100A\n6.100B\n6.1200';
      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.100A', units: 12 },
      ]);

      expect(tree.reqs).toHaveLength(3);
      expect(tree.reqs[0].fulfilled).toBe(true);
      expect(tree.reqs[1].fulfilled).toBe(false);
      expect(tree.reqs[2].fulfilled).toBe(false);
    });
  });

  describe('OR requirements', () => {
    it('should parse OR requirements with /', () => {
      const content = '6.1020/6.1040';
      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.1020', units: 12 },
      ]);

      expect(tree.reqs).toHaveLength(1);
      expect(tree.reqs[0]).toMatchObject({
        'connection-type': 'any',
        fulfilled: true,
      });
      expect(tree.reqs[0].reqs).toHaveLength(2);
    });

    it('should fulfill OR if any option is taken', () => {
      const content = '6.1020/6.1040/6.1060';
      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.1040', units: 12 },
      ]);

      expect(tree.reqs[0].fulfilled).toBe(true);
      expect(tree.reqs[0].sat_courses).toContain('6.1040');
    });

    it('should not fulfill OR if no option is taken', () => {
      const content = '6.1020/6.1040';
      const tree = buildRequirementTree('test', metadata, 'Description', content, []);

      expect(tree.reqs[0].fulfilled).toBe(false);
    });
  });

  describe('AND requirements', () => {
    it('should parse AND requirements with ,', () => {
      const content = '(6.100A,6.100B)';
      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.100A', units: 12 },
        { subject_id: '6.100B', units: 12 },
      ]);

      expect(tree.reqs).toHaveLength(1);
      expect(tree.reqs[0]).toMatchObject({
        'connection-type': 'all',
        fulfilled: true,
      });
    });

    it('should not fulfill AND if only some are taken', () => {
      const content = '(6.100A,6.100B)';
      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.100A', units: 12 },
      ]);

      expect(tree.reqs[0].fulfilled).toBe(false);
    });
  });

  describe('threshold requirements', () => {
    it('should parse course count thresholds', () => {
      const content = '{>=3}(6.3200,6.3700,6.3800,6.4100)';
      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.3200', units: 12 },
        { subject_id: '6.3700', units: 12 },
        { subject_id: '6.3800', units: 12 },
      ]);

      expect(tree.reqs).toHaveLength(1);
      expect(tree.reqs[0].threshold).toMatchObject({
        cutoff: 3,
        criterion: 'courses',
        type: '>=',
      });
      expect(tree.reqs[0].fulfilled).toBe(true);
      expect(tree.reqs[0].progress).toBe(3);
    });

    it('should parse unit thresholds', () => {
      const content = '{>=48u}(6.3200,6.3700,6.3800,6.4100)';
      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.3200', units: 12 },
        { subject_id: '6.3700', units: 12 },
        { subject_id: '6.3800', units: 12 },
        { subject_id: '6.4100', units: 12 },
      ]);

      expect(tree.reqs[0].threshold).toMatchObject({
        cutoff: 48,
        criterion: 'units',
        type: '>=',
      });
      expect(tree.reqs[0].fulfilled).toBe(true);
      expect(tree.reqs[0].progress).toBe(48);
    });

    it('should handle threshold syntax variations', () => {
      const cases = [
        { content: '{>=3}(A,B,C)', type: '>=' },
        { content: '{>2}(A,B,C)', type: '>' },
        { content: '{<=5}(A,B,C)', type: '<=' },
        { content: '{<4}(A,B,C)', type: '<' },
      ];

      cases.forEach(({ content, type }) => {
        const tree = buildRequirementTree('test', metadata, 'Description', content, []);
        expect(tree.reqs[0].threshold?.type).toBe(type);
      });
    });

    it('should handle threshold after parentheses', () => {
      const content = '(6.3200,6.3700,6.3800){>=2}';
      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.3200', units: 12 },
        { subject_id: '6.3700', units: 12 },
      ]);

      expect(tree.reqs[0].threshold).toMatchObject({
        cutoff: 2,
        criterion: 'courses',
        type: '>=',
      });
      expect(tree.reqs[0].fulfilled).toBe(true);
    });
  });

  describe('variable declarations', () => {
    it('should parse and expand variable declarations', () => {
      const content = `intro_music, "Intro Music" := 21M.011, 21M.013
samplings, "Samplings" := 21M.120, 21M.128
total, "Total" := (intro_music / samplings){>=1}`;

      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '21M.011', units: 12 },
      ]);

      // Should have one requirement (total)
      expect(tree.reqs).toHaveLength(1);
      
      // The requirement should be expanded with actual courses
      const totalReq = tree.reqs[0];
      expect(totalReq.threshold).toMatchObject({
        cutoff: 1,
        criterion: 'courses',
        type: '>=',
      });
      expect(totalReq.fulfilled).toBe(true);
    });

    it('should handle nested variable references', () => {
      const content = `group_a := 6.100A, 6.100B
group_b := 6.1020, 6.1040
all_groups := group_a / group_b
final := (all_groups){>=2}`;

      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.100A', units: 12 },
        { subject_id: '6.100B', units: 12 },
      ]);

      expect(tree.reqs).toHaveLength(1);
      expect(tree.reqs[0].fulfilled).toBe(true);
      expect(tree.reqs[0].progress).toBe(2);
    });

    it('should ignore variable title when expanding', () => {
      const content = `my_var, "Variable Title" := 6.100A, 6.100B
my_var`;

      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.100A', units: 12 },
        { subject_id: '6.100B', units: 12 },
      ]);

      // Should have one requirement that references the variable
      expect(tree.reqs).toHaveLength(1);
      expect(tree.reqs[0]).toMatchObject({
        'connection-type': 'all',
        fulfilled: true,
      });
    });
  });

  describe('complex nested requirements', () => {
    it('should handle deeply nested requirements', () => {
      const content = '(6.100A,(6.1020/6.1040))';
      const tree = buildRequirementTree('test', metadata, 'Description', content, [
        { subject_id: '6.100A', units: 12 },
        { subject_id: '6.1020', units: 12 },
      ]);

      expect(tree.reqs[0]['connection-type']).toBe('all');
      expect(tree.reqs[0].fulfilled).toBe(true);
      expect(tree.reqs[0].reqs).toHaveLength(2);
      expect(tree.reqs[0].reqs![1]['connection-type']).toBe('any');
    });
  });
});
