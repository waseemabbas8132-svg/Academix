import 'package:academix/features/assignments/data/models/ai_evaluation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('API decimal strings preserve suggested and teacher-approved values separately', () {
    final result = AIEvaluation.fromJson({
      'id': 'evaluation',
      'suggested_total': '8.00',
      'approved_marks': '6.00',
      'teacher_feedback': 'Reviewed original.',
      'maximum_marks': '10.00',
      'confidence': .8,
      'explanation': 'Reason.',
      'feedback': 'AI feedback.',
      'model_name': 'fake',
      'model_version': 'test',
      'review_status': 'approved',
      'question_evaluations': [
        {
          'question_id': 'q1',
          'suggested_marks': '8.00',
          'teacher_marks': '6.00',
          'maximum_marks': '10.00',
          'confidence': .8,
          'explanation': 'Reason.',
          'feedback': 'Feedback.',
          'evidence': [],
          'needs_review': false,
        },
      ],
      'feedback_items': [],
    });
    expect(result.suggestedTotal, 8);
    expect(result.approvedMarks, 6);
    expect(result.teacherFeedback, 'Reviewed original.');
    expect(result.questions.single.suggestedMarks, 8);
    expect(result.questions.single.teacherMarks, 6);
  });
}
