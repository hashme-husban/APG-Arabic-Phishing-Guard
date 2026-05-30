import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import 'app_surface_card.dart';

class BulletListCard extends StatelessWidget {
  final String title;
  final IconData icon;
  final List<String> items;
  final String Function(String text) translator;

  const BulletListCard({
    super.key,
    required this.title,
    required this.icon,
    required this.items,
    required this.translator,
  });

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();

    return AppSurfaceCard(
      padding: EdgeInsets.zero,
      child: Theme(
        data: Theme.of(context).copyWith(
          dividerColor: Colors.transparent,
          splashColor: Colors.transparent,
          highlightColor: Colors.transparent,
        ),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 4),
          childrenPadding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
          title: Row(
            children: [
              Icon(icon, size: 20),
              const SizedBox(width: 8),
              Text(
                title,
                style: Theme.of(
                  context,
                ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
              ),
            ],
          ),
          subtitle: Text('${items.length} ${context.l10n.itemsWord}'),
          children: items.map((item) {
            return Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(top: 3),
                    child: Text('• '),
                  ),
                  Expanded(
                    child: Text(
                      translator(item),
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                  ),
                ],
              ),
            );
          }).toList(),
        ),
      ),
    );
  }
}
