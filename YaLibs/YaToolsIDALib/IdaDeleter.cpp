//  Copyright (C) 2017 The YaCo Authors
//
//  This program is free software: you can redistribute it and/or modify
//  it under the terms of the GNU General Public License as published by
//  the Free Software Foundation, either version 3 of the License, or
//  (at your option) any later version.
//
//  This program is distributed in the hope that it will be useful,
//  but WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//  GNU General Public License for more details.
//
//  You should have received a copy of the GNU General Public License
//  along with this program.  If not, see <http://www.gnu.org/licenses/>.

#include <YaTypes.hpp>
#include "Ida.h"

#include "IdaDeleter.hpp"
#include "HVersion.hpp"
#include "Yatools.hpp"
#include "Helpers.h"
#include "YaHelpers.hpp"

#define LOG(LEVEL, FMT, ...) CONCAT(YALOG_, LEVEL)("ida_deleter", (FMT), ## __VA_ARGS__)

namespace
{
    void delete_struc(const HVersion& hver)
    {
        const auto name = make_string(hver.username());
        const auto struc = get_struc(get_struc_id(name.data()));
        if(!struc)
        {
            LOG(ERROR, "unable to delete missing struc '%s'\n", name.data());
            return;
        }
        const auto ok = del_struc(struc);
        if(!ok)
            LOG(ERROR, "unable to delete struc '%s'\n", name.data());
    }

    void delete_enum(const HVersion& hver)
    {
        const auto name = make_string(hver.username());
        const auto eid = get_enum(name.data());
        if(eid == BADADDR)
            LOG(ERROR, "unable to delete missing enum '%s'\n", name.data());
        else
            del_enum(eid);
    }

    void delete_enum_member(const HVersion& hver)
    {
        const auto name = make_string(hver.username());
        const auto cid = get_enum_member_by_name(name.data());
        if(cid == BADADDR)
        {
            LOG(ERROR, "unable to delete missing enum member '%s'\n", name.data());
            return;
        }
        const auto eid = get_enum_member_enum(cid);
        const auto value = get_enum_member_value(cid);
        const auto serial = get_enum_member_serial(cid);
        const auto bmask = get_enum_member_bmask(cid);
        const auto ok = del_enum_member(eid, value, serial, bmask);
        if(!ok)
            LOG(ERROR, "unable to delete enum member '%s'\n", name.data());
    }

    void delete_function(const HVersion& hver)
    {
        const auto ea = static_cast<ea_t>(hver.address());
        const auto ok = del_func(ea);
        if(!ok)
            LOG(ERROR, "unable to delete func 0x%0" EA_SIZE PRIXEA "\n", ea);
    }

    void delete_data(const HVersion& hver)
    {
        const auto ea = static_cast<ea_t>(hver.address());
        const auto ok = del_items(ea, DELIT_EXPAND);
        if(!ok)
            LOG(ERROR, "unable to delete data 0x%0" EA_SIZE PRIXEA "\n", ea);
    }

    void delete_code(const HVersion& hver)
    {
        const auto ea = static_cast<ea_t>(hver.address());
        const auto ok = del_items(ea, DELIT_EXPAND, static_cast<asize_t>(hver.size()));
        if(!ok)
            LOG(ERROR, "unable to delete code 0x%0" EA_SIZE PRIXEA "\n", ea);
    }

    void delete_block(const HVersion& hver)
    {
        const auto ea = static_cast<ea_t>(hver.address());
        const auto ok = del_items(ea, DELIT_EXPAND, static_cast<asize_t>(hver.size()));
        if(!ok)
            LOG(ERROR, "unable to delete basic block 0x%0" EA_SIZE PRIXEA "\n", ea);
    }

    void delete_object(const HVersion& hver)
    {
        switch(hver.type())
        {
            default:
                break;

            case OBJECT_TYPE_STRUCT:
                delete_struc(hver);
                break;

            case OBJECT_TYPE_ENUM:
                delete_enum(hver);
                break;

            case OBJECT_TYPE_ENUM_MEMBER:
                delete_enum_member(hver);
                break;

            case OBJECT_TYPE_FUNCTION:
                delete_function(hver);
                break;

            case OBJECT_TYPE_DATA:
                delete_data(hver);
                break;

            case OBJECT_TYPE_CODE:
                delete_code(hver);
                break;

            case OBJECT_TYPE_BASIC_BLOCK:
                delete_block(hver);
                break;
        }
    }
}

void delete_from_model(const IModel& model)
{
    model.walk([](const HVersion& hver)
    {
        ::delete_object(hver);
        return WALK_CONTINUE;
    });
}