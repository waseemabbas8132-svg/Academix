class RubricQuestion {
  const RubricQuestion({
    required this.questionId,
    required this.prompt,
    required this.maxMarks,
    this.modelAnswer,
    this.acceptableAnswers = const [],
    this.criteria = const [],
    this.partialCreditRules = const [],
  });

  final String questionId;
  final String prompt;
  final double maxMarks;
  final String? modelAnswer;
  final List<String> acceptableAnswers;
  final List<RubricCriterion> criteria;
  final List<String> partialCreditRules;

  factory RubricQuestion.fromJson(Map<String, dynamic> json) => RubricQuestion(
    questionId: json['question_id'] as String,
    prompt: json['prompt'] as String,
    maxMarks: _asDouble(json['max_marks']),
    modelAnswer: json['model_answer'] as String?,
    acceptableAnswers: _stringList(json['acceptable_answers']),
    criteria: (json['criteria'] as List<dynamic>? ?? [])
        .map((item) => RubricCriterion.fromJson(item as Map<String, dynamic>))
        .toList(),
    partialCreditRules: _stringList(json['partial_credit_rules']),
  );

  Map<String, dynamic> toJson() => {
    'question_id': questionId,
    'prompt': prompt,
    'max_marks': maxMarks,
    'model_answer': modelAnswer,
    'acceptable_answers': acceptableAnswers,
    'criteria': criteria.map((item) => item.toJson()).toList(),
    'partial_credit_rules': partialCreditRules,
  };
}

class RubricCriterion {
  const RubricCriterion({
    required this.description,
    required this.marks,
    required this.keywords,
    required this.concepts,
  });

  final String description;
  final double marks;
  final List<String> keywords;
  final List<String> concepts;

  factory RubricCriterion.fromJson(Map<String, dynamic> json) =>
      RubricCriterion(
        description: json['description'] as String,
        marks: _asDouble(json['marks']),
        keywords: _stringList(json['keywords']),
        concepts: _stringList(json['concepts']),
      );

  Map<String, dynamic> toJson() => {
    'description': description,
    'marks': marks,
    'keywords': keywords,
    'concepts': concepts,
  };
}

class AssignmentRubric {
  const AssignmentRubric({
    required this.id,
    required this.assignmentId,
    required this.questions,
    this.modelAnswer,
    this.teacherInstructions,
  });

  final String id;
  final String assignmentId;
  final String? modelAnswer;
  final String? teacherInstructions;
  final List<RubricQuestion> questions;

  factory AssignmentRubric.fromJson(Map<String, dynamic> json) =>
      AssignmentRubric(
        id: json['id'] as String,
        assignmentId: json['assignment_id'] as String,
        modelAnswer: json['model_answer'] as String?,
        teacherInstructions: json['teacher_instructions'] as String?,
        questions: (json['questions'] as List<dynamic>)
            .map(
              (item) => RubricQuestion.fromJson(item as Map<String, dynamic>),
            )
            .toList(),
      );
}

class ExtractedAnswer {
  const ExtractedAnswer({
    required this.segmentNumber,
    required this.text,
    required this.source,
    required this.needsReview,
    this.pageNumber,
    this.ocrConfidence,
  });

  final int segmentNumber;
  final int? pageNumber;
  final String text;
  final String source;
  final double? ocrConfidence;
  final bool needsReview;

  factory ExtractedAnswer.fromJson(Map<String, dynamic> json) =>
      ExtractedAnswer(
        segmentNumber: (json['segment_number'] as num).toInt(),
        pageNumber: (json['page_number'] as num?)?.toInt(),
        text: json['text'] as String,
        source: json['source'] as String,
        ocrConfidence: _asNullableDouble(json['ocr_confidence']),
        needsReview: json['needs_review'] as bool,
      );
}

class QuestionEvaluation {
  const QuestionEvaluation({
    required this.questionId,
    required this.maximumMarks,
    required this.confidence,
    required this.explanation,
    required this.feedback,
    required this.evidence,
    required this.needsReview,
    this.suggestedMarks,
    this.teacherMarks,
  });

  final String questionId;
  final double? suggestedMarks;
  final double? teacherMarks;
  final double maximumMarks;
  final double confidence;
  final String explanation;
  final String feedback;
  final List<String> evidence;
  final bool needsReview;

  factory QuestionEvaluation.fromJson(Map<String, dynamic> json) =>
      QuestionEvaluation(
        questionId: json['question_id'] as String,
        suggestedMarks: _asNullableDouble(json['suggested_marks']),
        teacherMarks: _asNullableDouble(json['teacher_marks']),
        maximumMarks: _asDouble(json['maximum_marks']),
        confidence: _asDouble(json['confidence']),
        explanation: json['explanation'] as String,
        feedback: json['feedback'] as String,
        evidence: _stringList(json['evidence']),
        needsReview: json['needs_review'] as bool,
      );
}

class AIEvaluation {
  const AIEvaluation({
    required this.id,
    required this.maximumMarks,
    required this.confidence,
    required this.explanation,
    required this.feedback,
    required this.modelName,
    required this.modelVersion,
    required this.reviewStatus,
    required this.questions,
    required this.feedbackItems,
    this.suggestedTotal,
    this.approvedMarks,
    this.teacherFeedback,
  });

  final String id;
  final double? suggestedTotal;
  final double? approvedMarks;
  final String? teacherFeedback;
  final double maximumMarks;
  final double confidence;
  final String explanation;
  final String feedback;
  final String modelName;
  final String modelVersion;
  final String reviewStatus;
  final List<QuestionEvaluation> questions;
  final List<EvaluationFeedback> feedbackItems;

  factory AIEvaluation.fromJson(Map<String, dynamic> json) => AIEvaluation(
    id: json['id'] as String,
    suggestedTotal: _asNullableDouble(json['suggested_total']),
    approvedMarks: _asNullableDouble(json['approved_marks']),
    teacherFeedback: json['teacher_feedback'] as String?,
    maximumMarks: _asDouble(json['maximum_marks']),
    confidence: _asDouble(json['confidence']),
    explanation: json['explanation'] as String,
    feedback: json['feedback'] as String,
    modelName: json['model_name'] as String,
    modelVersion: json['model_version'] as String,
    reviewStatus: json['review_status'] as String,
    questions: (json['question_evaluations'] as List<dynamic>)
        .map(
          (item) => QuestionEvaluation.fromJson(item as Map<String, dynamic>),
        )
        .toList(),
    feedbackItems: (json['feedback_items'] as List<dynamic>)
        .map(
          (item) => EvaluationFeedback.fromJson(item as Map<String, dynamic>),
        )
        .toList(),
  );
}

class EvaluationFeedback {
  const EvaluationFeedback({
    required this.kind,
    required this.message,
    required this.details,
    this.similarityScore,
    this.otherSubmissionId,
  });

  final String kind;
  final String message;
  final double? similarityScore;
  final String? otherSubmissionId;
  final Map<String, dynamic> details;

  factory EvaluationFeedback.fromJson(Map<String, dynamic> json) =>
      EvaluationFeedback(
        kind: json['kind'] as String,
        message: json['message'] as String,
        similarityScore: _asNullableDouble(json['similarity_score']),
        otherSubmissionId: json['other_submission_id'] as String?,
        details: (json['details'] as Map<String, dynamic>? ?? {}),
      );
}

class EvaluationJob {
  const EvaluationJob({
    required this.id,
    required this.submissionId,
    required this.status,
    required this.attemptCount,
    required this.extractedAnswers,
    this.errorSummary,
    this.evaluation,
  });

  final String id;
  final String submissionId;
  final String status;
  final int attemptCount;
  final String? errorSummary;
  final List<ExtractedAnswer> extractedAnswers;
  final AIEvaluation? evaluation;

  factory EvaluationJob.fromJson(Map<String, dynamic> json) => EvaluationJob(
    id: json['id'] as String,
    submissionId: json['submission_id'] as String,
    status: json['status'] as String,
    attemptCount: (json['attempt_count'] as num).toInt(),
    errorSummary: json['error_summary'] as String?,
    extractedAnswers: (json['extracted_answers'] as List<dynamic>)
        .map((item) => ExtractedAnswer.fromJson(item as Map<String, dynamic>))
        .toList(),
    evaluation: json['evaluation'] == null
        ? null
        : AIEvaluation.fromJson(json['evaluation'] as Map<String, dynamic>),
  );
}

double _asDouble(Object? value) =>
    value is num ? value.toDouble() : double.parse(value.toString());

double? _asNullableDouble(Object? value) =>
    value == null ? null : _asDouble(value);

List<String> _stringList(Object? value) =>
    (value as List<dynamic>? ?? []).cast<String>();
