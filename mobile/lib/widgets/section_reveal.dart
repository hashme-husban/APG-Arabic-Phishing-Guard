import 'package:flutter/material.dart';

class SectionReveal extends StatelessWidget {
  final Widget child;
  final int index;

  const SectionReveal({super.key, required this.child, required this.index});

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 0, end: 1),
      duration: Duration(milliseconds: 320 + (index * 120)),
      curve: Curves.easeOutCubic,
      builder: (context, value, builtChild) {
        return Opacity(
          opacity: value,
          child: Transform.translate(
            offset: Offset(0, (1 - value) * 18),
            child: builtChild,
          ),
        );
      },
      child: child,
    );
  }
}
