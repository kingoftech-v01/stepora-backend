import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'config/routes.dart';
import 'core/theme/app_theme.dart';
import 'providers/theme_provider.dart';
import 'providers/locale_provider.dart';

class DreamPlannerApp extends ConsumerWidget {
  const DreamPlannerApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    final themeMode = ref.watch(themeProvider);
    final locale = ref.watch(localeProvider);

    return MaterialApp.router(
      title: 'DreamPlanner',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: themeMode,
      locale: locale,
      routerConfig: router,
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: const [
        Locale('en'),
        Locale('fr'),
        Locale('es'),
        Locale('de'),
        Locale('it'),
        Locale('pt'),
        Locale('ja'),
        Locale('ko'),
        Locale('zh'),
        Locale('ar'),
        Locale('hi'),
        Locale('ru'),
        Locale('tr'),
        Locale('nl'),
        Locale('pl'),
      ],
    );
  }
}
