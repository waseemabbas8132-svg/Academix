import 'package:academix/features/assignments/data/repositories/demo_ai_evaluation_repository.dart';
import 'package:flutter/material.dart';

class DemoSubmissionPreviewScreen extends StatelessWidget {
  const DemoSubmissionPreviewScreen({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Original submission · Demo fixture')),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          color: Theme.of(context).colorScheme.errorContainer,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              demoAIFixtureDisclosure,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Synthetic handwritten-page previews bundled with the app. These are not student uploads and were not processed by OCR.',
        ),
        for (var index = 0; index < demoHandwrittenPageAssets.length; index++)
          Card(
            clipBehavior: Clip.antiAlias,
            margin: const EdgeInsets.symmetric(vertical: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ListTile(
                  leading: const Icon(Icons.image_outlined),
                  title: Text('Handwritten sample · Page ${index + 1}'),
                  subtitle: const Text('Synthetic PNG demonstration asset'),
                ),
                Image.asset(
                  demoHandwrittenPageAssets[index],
                  fit: BoxFit.contain,
                  semanticLabel:
                      'Synthetic handwritten submission sample, page ${index + 1}',
                ),
              ],
            ),
          ),
      ],
    ),
  );
}
