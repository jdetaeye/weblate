# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-04 14:37
from __future__ import unicode_literals

from django.core.management.sql import emit_post_migrate_signal
from django.db import migrations

from weblate.permissions.data import DEFAULT_GROUPS, ADMIN_PERMS, ADMIN_ONLY_PERMS


def migrate_acl(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    Project = apps.get_model('trans', 'Project')
    GroupACL = apps.get_model('permissions', 'GroupACL')

    # Workaround to ensure the permission added in 0083_auto_20170404_1633
    # is actually created, see https://code.djangoproject.com/ticket/23422
    emit_post_migrate_signal(0, False, schema_editor.connection.alias)

    groups = {}
    all_perms = Permission.objects.filter(codename__in=ADMIN_PERMS)
    admin_perms = Permission.objects.filter(codename__in=ADMIN_ONLY_PERMS)

    # Create default @ groups
    # This is stripped down version of create_groups
    for name in DEFAULT_GROUPS:
        if name[0] != '@':
            continue
        group, created = Group.objects.get_or_create(name=name)
        if created:
            group.permissions.set(
                Permission.objects.filter(codename__in=DEFAULT_GROUPS[name])
            )
        groups[name] = group.permissions.all()

    # Create ACL groups for ACL enabled projects
    for project in Project.objects.iterator():
        # Create GroupACL object
        group_acl = GroupACL.objects.get_or_create(project=project)[0]
        if project.enable_acl:
            group_acl.permissions.set(all_perms)
            old_group = Group.objects.get(name=project.name)
            project_groups = groups.keys()
        else:
            group_acl.permissions.set(admin_perms)
            old_group = None
            project_groups = ['@Administration']

        # Create groups
        for name in project_groups:
            groupname = '{0}{1}'.format(project.name, name)
            group = Group.objects.get_or_create(name=groupname)[0]
            group.permissions.set(groups[name])

            # Add GroupACL assignment
            group_acl.groups.add(group)

            # Migrate ACL assignments
            if name == '@Administration':
                group.user_set.add(*project.owners.all())
            elif old_group:
                # Users had all access before
                group.user_set.add(*old_group.user_set.all())

        # Remove no longer needed group
        if old_group:
            old_group.delete()

    # Delete no longer needed ACL permissions
    Permission.objects.filter(codename__startswith='weblate_acl_').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('permissions', '0005_groupacl_permissions'),
        ('trans', '0083_auto_20170404_1633'),
        ('screenshots', '0003_auto_20170215_1633'),
    ]

    operations = [
        migrations.RunPython(migrate_acl),
    ]
