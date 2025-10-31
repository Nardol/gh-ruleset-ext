# gh-ruleset-ext

> Documentation française de l’extension GitHub CLI pour gérer les Rulesets.  
> 🇬🇧 For the English overview, see [README.md](README.md).

Extension `gh` pour gérer de bout en bout les rulesets GitHub d’un dépôt. Elle permet de :

> ℹ️ GitHub CLI propose déjà une commande basique `gh ruleset`. `gh ruleset-ext` ajoute des assistants interactifs et la découverte automatique des checks.

- lister et inspecter les rulesets existants ;
- créer, modifier ou supprimer un ruleset ;
- ajouter, modifier ou retirer une règle individuelle ;
- configurer interactivement les checks de statut requis (`required_status_checks`) grâce à l’autodiscovery des checks récemment exécutés (branche par défaut, PR ouverte/fusionnée la plus récente, refs personnalisées) ;
- éditer ou compléter n’importe quel rule set au format JSON (via `--file` ou l’éditeur défini dans `EDITOR` / `VISUAL`).

> ℹ️ L’API Rulesets nécessite des droits **Admin** sur le dépôt ciblé. Les commandes échoueront pour un dépôt sur lequel vous n’êtes pas administrateur.

## Installation

```bash
gh extension install Nardol/gh-ruleset-ext
```

En développement local, il suffit d’exécuter `./gh-ruleset-ext …`. Une fois le repo cloné, vous pouvez tester l’extension avant publication avec :

```bash
gh extension install .
```

## Dépendances

- GitHub CLI ≥ 2.43 (nécessaire pour `gh api` et les rulesets) ;
- Python ≥ 3.10 (fourni sur macOS/Linux récents) ;
- L’extension se repose sur le token utilisé par `gh`. Vérifiez avec `gh auth status`.

## Utilisation rapide

Chaque commande accepte `--repo OWNER/REPO` (ou `HOST/OWNER/REPO`). Sans précision, le dépôt courant (`gh repo view`) est utilisé.

```bash
# Lister les rulesets
gh ruleset-ext list

# Voir le détail complet d’un ruleset
gh ruleset-ext view 42

# Créer interactivement un nouveau ruleset
gh ruleset-ext create

# Modifier un ruleset existant (assistant interactif)
gh ruleset-ext update 42

# Gérer les règles individuellement
gh ruleset-ext rule list 42
gh ruleset-ext rule add 42
gh ruleset-ext rule edit 42 1
gh ruleset-ext rule delete 42 2

# Découvrir les checks récemment observés (utile pour required_status_checks)
gh ruleset-ext checks --repo owner/repo
gh ruleset-ext checks --pr 42            # inclut la PR #42
gh ruleset-ext checks --latest-pr        # ajoute la PR ouverte la plus récente (puis fusionnée sinon)
gh ruleset-ext checks --no-default --ref 123abc456  # SHA précis sans la branche par défaut
```

### Création / modification interactive

L’assistant vous guide sur :

1. **Nom, cible et mode d’application** (`disabled`, `evaluate`, `active`).
2. **Conditions ref_name** : vous pouvez indiquer des patterns simples (par ex. `main`, `release/*`). L’assistant ajoute automatiquement `refs/heads/` ou `refs/tags/`.
3. **Acteurs autorisés à contourner** (RepositoryRole, Team, Integration, OrganizationAdmin, EnterpriseAdmin) avec gestion du mode (`always` ou `pull_request`).
4. **Règles** :
   - Ajout rapide d’une règle `required_status_checks` avec sélection guidée :
     - lister les checks observés (branche par défaut, PR ouverte/fusionnée la plus récente, PR supplémentaires ou refs de votre choix) avec l’ID d’intégration (GitHub App) quand il est disponible ;
     - ajouter/supprimer des checks, préciser un `integration_id` si nécessaire ;
     - configurer `strict_required_status_checks_policy` et `do_not_enforce_on_create`.
   - Édition libre au format JSON pour toutes les autres règles (templates pré-remplis).

Vous pouvez toujours compléter ou corriger le JSON final via `--editor` (ouvre `$EDITOR`) ou `--file chemin.json`.

### Mode fichier / JSON brut

- `--file ruleset.json` : charge un JSON existant (exporté via `gh ruleset-ext view --json` par exemple).
- `--editor` après l’assistant : ouvre l’objet final dans votre éditeur avant de l’envoyer à l’API.
- `gh ruleset-ext create --from-existing ID` : clone un ruleset avant de lancer l’assistant.

## Notes sur les règles et bypass

- Les règles `required_status_checks` suivent la structure officielle de l’API :
  ```json
  {
    "type": "required_status_checks",
    "parameters": {
      "required_status_checks": [
        {"context": "build", "integration_id": 123}
      ],
      "strict_required_status_checks_policy": true,
      "do_not_enforce_on_create": false
    }
  }
  ```
- Les acteurs pouvant contourner (`bypass_actors`) acceptent les types :
  - `RepositoryRole` (champ `repository_role_name`) ;
  - `Team` (champ `actor_id`, récupéré automatiquement via `gh api`) ;
  - `Integration` (`actor_id`) ;
  - `OrganizationAdmin` ou `EnterpriseAdmin`.
- Lors du choix des checks requis, l’assistant affiche l’`integration_id` (GitHub App) quand il est disponible, ce qui vous permet de verrouiller la provenance du check. Vous pouvez bien sûr le saisir manuellement si besoin.

Référez-vous à la documentation GitHub pour l’exhaustivité des paramètres des règles : `gh ruleset-ext view --json` fournit une base modifiable, et l’édition JSON libre permet d’utiliser toutes les fonctionnalités disponibles.

## Dépannage

- `GH_TOKEN`/`GITHUB_TOKEN` insuffisant : assurez-vous d’avoir un PAT ou une authentification `gh` avec permission `Administration`.
- Team introuvable : utilisez le format `ORG/slug` et vérifiez que vous avez accès à l’organisation.
- Aucune découverte de checks : les checks sont collectés sur le dernier commit de la branche par défaut ; assurez-vous qu’un workflow ou un statut a déjà été exécuté sur cette branche.

## Roadmap / idées

- Support optionnel de la génération YAML pour partager des rulesets.
- Validation locale des règles via le schéma OpenAPI.
- Suggestions automatiques pour d’autres types de règles (par ex. `pull_request`, `actor_allow_list`).

Les contributions sont bienvenues ! Voir `CONTRIBUTING.md` pour démarrer. La licence est MIT (voir `LICENSE`).

---

### Note éthique

Ce dépôt est développé avec l’aide d’OpenAI Codex (GPT‑5). Chaque commit est relu manuellement avant publication.
